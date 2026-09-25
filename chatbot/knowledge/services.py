from audit.services import record
from django.db import transaction
from projects.models import Role
from projects.policies import authorized_bases, authorized_policies
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .embeddings import embedding_provider
from .models import Document, DocumentChunk


def chunk_text(text, size=1200, overlap=150):
    if not text.strip() or "\x00" in text:
        raise ValidationError("Provide nonempty plain text without null bytes.")
    return [text[start : start + size] for start in range(0, len(text), size - overlap)]


def ingest(membership, base_id, *, title, text, policy_id):
    if membership.role < Role.EDITOR:
        raise PermissionDenied("Editor role required.")
    base = authorized_bases(membership).filter(pk=base_id).first()
    policy = authorized_policies(membership).filter(pk=policy_id).first()
    if base is None or policy is None:
        raise NotFound("Knowledge base or policy not found.")
    if len(text) > 200000:
        raise ValidationError("Document exceeds 200000 characters.")
    chunks = chunk_text(text)
    embedder = embedding_provider()
    vectors = []
    for start in range(0, len(chunks), 16):
        vectors.extend(embedder.embed(chunks[start : start + 16]))
    with transaction.atomic():
        document = Document.objects.create(
            project=membership.project,
            knowledge_base=base,
            policy=policy,
            title=title,
            embedding_model=embedder.identity,
        )
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(document=document, ordinal=i, text=chunk, embedding=vector)
                for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
        )
        record(
            "document_ingested",
            project=membership.project,
            user=membership.user,
            metadata={"document_ids": [document.pk], "knowledge_base_ids": [base.pk]},
        )
    return document
