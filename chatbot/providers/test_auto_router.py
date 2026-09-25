import json
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, override_settings

from .auto_router import AutoRouteDecision, JevRouter, choose_auto_route, sanitize_prompt
from .router import RouteDecision, prioritize


@override_settings(
    JEV_ROUTER_URL="https://openrouter.ai/api/alpha/decisions",
    JEV_ROUTER_KEY="test-router-key",
    JEV_ROUTER_MODEL="typesafe/jev-1.13",
    JEV_ROUTER_TIMEOUT=8,
    JEV_ROUTER_MIN_CONFIDENCE=0.7,
)
class AutoRouterTests(SimpleTestCase):
    def test_scrubber_replaces_credentials_and_pii(self):
        result = sanitize_prompt(
            "authorization: Bearer abcdefghijklmnop email me at person@example.com from 192.168.1.2"
        )
        self.assertTrue(result.contains_secret)
        self.assertNotIn("abcdefghijklmnop", result.text)
        self.assertNotIn("person@example.com", result.text)
        self.assertNotIn("192.168.1.2", result.text)
        self.assertIn("<SECRET>", result.text)
        self.assertIn("<EMAIL>", result.text)

    def test_jev_choice_is_validated(self):
        captured = []

        def handle(request):
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "answers": {
                        "route": {
                            "type": "choice",
                            "choice": "external",
                            "confidence": 0.94,
                            "probabilities": {"local": 0.06, "external": 0.94},
                        }
                    }
                },
            )

        router = JevRouter()
        with patch.object(router, "client", return_value=httpx.Client(transport=httpx.MockTransport(handle))):
            decision = router.decide("Debug this transaction race")

        self.assertEqual(decision, AutoRouteDecision("external", "jev_external", 0.94))
        self.assertEqual(captured[0]["model"], "typesafe/jev-1.13")
        self.assertEqual(captured[0]["state"], "Debug this transaction race")
        self.assertEqual(set(captured[0]["questions"]["route"]["criteria"]), {"local", "external"})

    def test_low_confidence_and_malformed_responses_fall_back_local(self):
        low = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"answers": {"route": {"type": "choice", "choice": "external", "confidence": 0.4}}},
            )
        )
        malformed = httpx.MockTransport(lambda request: httpx.Response(200, json={"unexpected": True}))
        router = JevRouter()
        with patch.object(router, "client", return_value=httpx.Client(transport=low)):
            self.assertEqual(router.decide("ambiguous").reason, "jev_low_confidence")
        with patch.object(router, "client", return_value=httpx.Client(transport=malformed)):
            self.assertEqual(router.decide("ambiguous").reason, "jev_unavailable")

    def test_string_confidence_is_rejected(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"answers": {"route": {"type": "choice", "choice": "external", "confidence": "0.94"}}},
            )
        )
        router = JevRouter()
        with patch.object(router, "client", return_value=httpx.Client(transport=transport)):
            self.assertEqual(router.decide("ambiguous").reason, "jev_unavailable")

    def test_secret_forces_local_without_calling_jev(self):
        with patch("providers.auto_router.JevRouter.decide") as decide:
            result = choose_auto_route("password=very-secret-password", {"local", "external"})
        self.assertEqual(result.preferred_mode, "local")
        self.assertTrue(result.local_only)
        decide.assert_not_called()

    def test_single_available_mode_skips_jev(self):
        with patch("providers.auto_router.JevRouter.decide") as decide:
            local = choose_auto_route("hello", {"local"})
            external = choose_auto_route("hello", {"external"})
        self.assertEqual(local.preferred_mode, "local")
        self.assertEqual(external.preferred_mode, "external")
        decide.assert_not_called()

    def test_preference_reorders_candidates_and_can_block_external(self):
        local_model = SimpleNamespace(provider=SimpleNamespace(connection_alias="local"))
        external_model = SimpleNamespace(provider=SimpleNamespace(connection_alias="external"))
        decisions = [
            RouteDecision(local_model, True, "permitted"),
            RouteDecision(external_model, True, "permitted"),
        ]
        routed = prioritize(decisions, "external")
        self.assertIs(routed[0].model, external_model)
        local_only = prioritize(decisions, "local", local_only=True)
        self.assertFalse(local_only[1].allowed)
        self.assertEqual(local_only[1].reason, "router_local_only")
