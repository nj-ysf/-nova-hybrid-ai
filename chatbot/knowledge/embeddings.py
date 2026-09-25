import hashlib
import math
import re
from abc import ABC, abstractmethod

import httpx
from django.conf import settings
from django.utils.module_loading import import_string
from providers.base import ProviderError


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def identity(self) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddings(EmbeddingProvider):
    @property
    def identity(self):
        return settings.EMBEDDING_MODEL

    def embed(self, texts):
        if "cloud" in self.identity.lower() or "://" in self.identity:
            raise ProviderError()
        try:
            with httpx.Client(
                timeout=settings.PROVIDER_TIMEOUT, trust_env=False, follow_redirects=False
            ) as client:
                response = client.post(
                    settings.EMBEDDING_URL.rstrip("/") + "/api/embed",
                    json={
                        "model": self.identity,
                        "input": texts,
                        "truncate": False,
                    },
                )
                response.raise_for_status()
                vectors = response.json()["embeddings"]
            if len(vectors) != len(texts):
                raise ValueError
            for vector in vectors:
                if (
                    len(vector) != settings.EMBEDDING_DIMENSIONS
                    or not all(math.isfinite(v) for v in vector)
                    or not any(vector)
                ):
                    raise ValueError
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise ProviderError() from None


class HashEmbeddings(EmbeddingProvider):
    """Deterministic test double; deliberately not a production semantic model."""

    identity = "test-hash-768"

    def embed(self, texts):
        result = []
        for text in texts:
            vector = [0.0] * 768
            for word in re.findall(r"\w+", text.lower()) or ["empty"]:
                index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % 768
                vector[index] += 1
            norm = math.sqrt(sum(v * v for v in vector))
            result.append([v / norm for v in vector])
        return result


def embedding_provider() -> EmbeddingProvider:
    return import_string(settings.EMBEDDING_BACKEND)()
