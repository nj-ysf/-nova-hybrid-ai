from django.conf import settings

from .base import ProviderError
from .langchain import GeminiProvider, OllamaProvider

PROVIDERS = {"ollama": OllamaProvider, "gemini": GeminiProvider}


def connection_for(model):
    return settings.LLM_CONNECTIONS.get(model.provider.connection_alias, {})


def connection_is_configured(connection):
    backend = connection.get("backend")
    return bool(connection.get("url")) if backend == "ollama" else bool(connection.get("key"))


def create_provider(model):
    connection = connection_for(model)
    factory = PROVIDERS.get(connection.get("backend"))
    if factory is None or not connection_is_configured(connection):
        raise ProviderError()
    return factory(model, connection)
