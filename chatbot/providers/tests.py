from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from .base import Generation, ProviderError, Turn
from .graph import run_model
from .langchain import GeminiProvider, OllamaProvider
from .registry import connection_is_configured


class LangChainProviderTests(SimpleTestCase):
    model = SimpleNamespace(name="test-model", context_tokens=8192)

    def local(self, chat_model=None):
        with patch("providers.langchain.ChatOllama", return_value=chat_model or Mock()) as factory:
            provider = OllamaProvider(
                self.model,
                {"url": "http://localhost:11434", "mode": "local", "key": ""},
            )
        return provider, factory

    def external(self, chat_model=None):
        with patch(
            "providers.langchain.ChatGoogleGenerativeAI", return_value=chat_model or Mock()
        ) as factory:
            provider = GeminiProvider(
                self.model,
                {"mode": "external", "key": "test-secret"},
            )
        return provider, factory

    def test_ollama_generate_maps_messages_limit_and_usage(self):
        chat_model = Mock()
        bound = chat_model.model_copy.return_value
        bound.invoke.return_value = AIMessage(
            content="hello", usage_metadata={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}
        )
        provider, factory = self.local(chat_model)

        result = provider.generate([Turn("system", "rules"), Turn("user", "hi")], max_tokens=10)

        self.assertEqual(result, Generation("hello", 2, 1))
        factory.assert_called_once_with(
            model="test-model",
            base_url="http://localhost:11434",
            num_ctx=8192,
            temperature=0,
            validate_model_on_init=False,
            client_kwargs={"timeout": 60, "trust_env": False},
        )
        chat_model.model_copy.assert_called_once_with(update={"num_predict": 10})
        sent = bound.invoke.call_args.args[0]
        self.assertIsInstance(sent[0], SystemMessage)
        self.assertIsInstance(sent[1], HumanMessage)

    def test_gemini_uses_developer_api_and_key(self):
        provider, factory = self.external()
        self.assertIsInstance(provider, GeminiProvider)
        factory.assert_called_once_with(
            model="test-model",
            api_key="test-secret",
            vertexai=False,
            timeout=60,
            max_retries=1,
        )

    def test_stream_yields_langchain_chunks(self):
        chat_model = Mock()
        chat_model.model_copy.return_value.stream.return_value = [
            AIMessageChunk(content="hel"),
            AIMessageChunk(content="lo"),
        ]
        provider, _ = self.local(chat_model)
        self.assertEqual(list(provider.stream([Turn("user", "hi")], max_tokens=10)), ["hel", "lo"])

    def test_malformed_response_is_sanitized(self):
        provider, _ = self.external()
        with (
            patch.object(provider, "_invoke", return_value=AIMessage(content="")),
            self.assertRaises(ProviderError) as error,
        ):
            provider.generate([Turn("user", "hi")], max_tokens=10)
        self.assertEqual(str(error.exception), "Model service unavailable.")

    def test_sdk_exception_is_sanitized(self):
        provider, _ = self.external()
        with (
            patch.object(provider, "_invoke", side_effect=RuntimeError("test-secret private prompt")),
            self.assertRaises(ProviderError) as error,
        ):
            provider.generate([Turn("user", "hi")], max_tokens=10)
        self.assertNotIn("test-secret", str(error.exception))
        self.assertNotIn("private prompt", str(error.exception))

    def test_invalid_role_is_rejected(self):
        provider, _ = self.local()
        with self.assertRaises(ProviderError):
            provider.generate([Turn("tool", "untrusted")], max_tokens=10)

    def test_invalid_ollama_url_is_rejected(self):
        with self.assertRaises(ProviderError):
            OllamaProvider(
                self.model,
                {"url": "http://user:password@localhost:11434", "mode": "local", "key": ""},
            )

    def test_missing_gemini_key_is_unconfigured(self):
        self.assertFalse(connection_is_configured({"backend": "gemini", "key": ""}))
        self.assertTrue(connection_is_configured({"backend": "gemini", "key": "set"}))


class ModelGraphTests(SimpleTestCase):
    def test_graph_executes_authorized_provider_once(self):
        provider = Mock()
        provider.generate.return_value = Generation("answer", 3, 2)
        messages = [Turn("user", "hello")]

        result = run_model(provider, messages, 25)

        self.assertEqual(result.text, "answer")
        provider.generate.assert_called_once_with(messages, max_tokens=25)
