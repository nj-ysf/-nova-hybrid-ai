from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from pgvector.django import CosineDistance
from projects.policies import authorized_documents

from .embeddings import embedding_provider
from .models import DocumentChunk


class Retriever(ABC):
    @abstractmethod
    def search(self, membership, query: str, *, top_k: int, base_ids=None): ...


class PgVectorRetriever(Retriever):
    def search(self, membership, query, *, top_k, base_ids=None):
        embedder = embedding_provider()
        documents = authorized_documents(membership).filter(embedding_model=embedder.identity)
        if base_ids is not None:
            documents = documents.filter(knowledge_base_id__in=base_ids)
        # SQL subquery filters authorization BEFORE distance ordering/LIMIT.
        chunks = DocumentChunk.objects.filter(document_id__in=documents.values("pk")).select_related(
            "document__policy",
            "document__knowledge_base__policy",
        )
        if not chunks.exists():
            return []
        vector = embedder.embed([query])[0]
        if connection.vendor == "postgresql":
            return list(
                chunks.annotate(distance=CosineDistance("embedding", vector)).order_by("distance", "pk")[
                    :top_k
                ]
            )
        if not settings.ALLOW_SQLITE_RETRIEVAL:
            raise ImproperlyConfigured("Production retrieval requires PostgreSQL + pgvector.")
        # SQLite dev/test fallback only materializes already authorized rows.
        import math

        def distance(chunk):
            stored = chunk.embedding
            denominator = math.sqrt(sum(v * v for v in stored) * sum(v * v for v in vector))
            return (
                1 - sum(a * b for a, b in zip(stored, vector, strict=True)) / denominator
                if denominator
                else 1
            )

        return sorted(chunks, key=lambda chunk: (distance(chunk), chunk.pk))[:top_k]
