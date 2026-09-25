"""LangChain chat-model adapters with a small, provider-neutral surface."""

from collections.abc import Sequence
from urllib.parse import urlsplit

from django.conf import settings
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from .base import Generation, LLMProvider, ProviderError, Turn


def _messages(turns: Sequence[Turn]) -> list[BaseMessage]:
    classes = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    try:
        return [classes[turn.role](content=turn.content) for turn in turns]
    except (KeyError, TypeError, ValueError):
        raise ProviderError() from None


def _text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        return "".join(
            block.get("text", "")
            for block in message.content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


class LangChainChatProvider(LLMProvider):
    output_option = "max_tokens"

    def __init__(self, model, connection):
        self.model = model.name
        self.context_tokens = model.context_tokens
        self._chat_model = self.build_model(model, connection)

    def build_model(self, model, connection):
        raise NotImplementedError

    def _bound_model(self, max_tokens):
        return self._chat_model.bind(**{self.output_option: max_tokens})

    def _invoke(self, messages, max_tokens):
        return self._bound_model(max_tokens).invoke(messages)

    def _stream(self, messages, max_tokens):
        return self._bound_model(max_tokens).stream(messages)

    def generate(self, messages, *, max_tokens):
        try:
            response = self._invoke(_messages(messages), max_tokens)
            text = _text(response).strip()
            if not text or len(text) > 100000:
                raise ValueError
            usage = response.usage_metadata or {}
            metadata = response.response_metadata or {}
            input_tokens = int(
                usage.get("input_tokens", metadata.get("prompt_eval_count", self.estimate_tokens(messages)))
            )
            output_tokens = int(
                usage.get("output_tokens", metadata.get("eval_count", len(text.encode("utf-8"))))
            )
            if min(input_tokens, output_tokens) < 0:
                raise ValueError
            return Generation(text, input_tokens, output_tokens)
        except ProviderError:
            raise
        except Exception:
            # Provider/SDK exceptions may contain credentials or prompt data.
            raise ProviderError() from None

    def stream(self, messages, *, max_tokens):
        try:
            total = 0
            for chunk in self._stream(_messages(messages), max_tokens):
                piece = _text(chunk)
                total += len(piece)
                if total > 100000:
                    raise ValueError
                if piece:
                    yield piece
        except ProviderError:
            raise
        except Exception:
            raise ProviderError() from None

    def health_check(self):
        try:
            response = self._invoke([HumanMessage(content="Reply only: ok")], 2)
            return bool(_text(response).strip())
        except Exception:
            return False


class OllamaProvider(LangChainChatProvider):
    output_option = "num_predict"

    def _bound_model(self, max_tokens):
        # ChatOllama exposes generation options as model fields. Passing
        # num_predict through bind() forwards it to Client.chat(), where the
        # current Ollama SDK rejects it as an unexpected keyword argument.
        return self._chat_model.model_copy(update={self.output_option: max_tokens})

    def build_model(self, model, connection):
        url = urlsplit(connection["url"])
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ProviderError()
        return ChatOllama(
            model=model.name,
            base_url=connection["url"].rstrip("/"),
            num_ctx=model.context_tokens,
            temperature=0,
            validate_model_on_init=False,
            client_kwargs={"timeout": settings.PROVIDER_TIMEOUT, "trust_env": False},
        )


class GeminiProvider(LangChainChatProvider):
    def build_model(self, model, connection):
        key = connection.get("key")
        if not key:
            raise ProviderError()
        return ChatGoogleGenerativeAI(
            model=model.name,
            api_key=key,
            vertexai=False,
            timeout=settings.PROVIDER_TIMEOUT,
            max_retries=1,
        )
