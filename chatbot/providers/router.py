from dataclasses import dataclass

from .registry import connection_for, connection_is_configured


@dataclass(frozen=True)
class RouteDecision:
    model: object
    allowed: bool
    reason: str


def evaluate(model, membership, classification, mode="auto", stream=False):
    project = membership.project
    if not membership.active or not project.enabled:
        return RouteDecision(model, False, "inactive")
    if model.project_id != project.pk or model.provider.project_id != project.pk:
        return RouteDecision(model, False, "project_mismatch")
    if not model.enabled or not model.provider.enabled or not model.provider.available:
        return RouteDecision(model, False, "disabled_or_unavailable")
    connection = connection_for(model)
    provider_mode = connection.get("mode")
    if provider_mode == "local" and ("cloud" in model.name.lower() or "://" in model.name):
        return RouteDecision(model, False, "local_model_required")
    if provider_mode not in ("local", "external") or not connection_is_configured(connection):
        return RouteDecision(model, False, "unconfigured")
    if mode != "auto" and mode != provider_mode:
        return RouteDecision(model, False, "requested_mode")
    if stream and not model.supports_streaming:
        return RouteDecision(model, False, "streaming_unsupported")
    if classification > membership.clearance:
        return RouteDecision(model, False, "clearance")
    if provider_mode == "external" and (
        not project.allow_external
        or not membership.can_use_external
        or classification > project.external_max_classification
    ):
        return RouteDecision(model, False, "external_policy")
    return RouteDecision(model, True, "permitted")


def candidates(agent, membership, classification, mode="auto"):
    models = [agent.primary_model]
    if agent.fallback_model_id and agent.fallback_model_id != agent.primary_model_id:
        models.append(agent.fallback_model)
    return [evaluate(model, membership, classification, mode) for model in models]


def prioritize(decisions, preferred_mode, *, local_only=False):
    routed = []
    for decision in decisions:
        provider_mode = connection_for(decision.model).get("mode")
        if local_only and provider_mode == "external" and decision.allowed:
            decision = RouteDecision(decision.model, False, "router_local_only")
        routed.append(decision)
    return sorted(
        routed,
        key=lambda decision: connection_for(decision.model).get("mode") != preferred_mode,
    )
