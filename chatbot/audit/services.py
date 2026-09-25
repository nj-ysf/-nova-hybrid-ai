from .models import AuditLog

SAFE_FIELDS = {
    "status",
    "provider_id",
    "model_id",
    "conversation_id",
    "knowledge_base_ids",
    "document_ids",
    "chunk_ids",
    "reason",
    "usage_id",
}


def record(event, *, project=None, user=None, metadata=None):
    """Only identifiers and application reason codes, never content or exception text."""
    return AuditLog.objects.create(
        event=event,
        project=project,
        user=user if getattr(user, "is_authenticated", False) else None,
        metadata={key: value for key, value in (metadata or {}).items() if key in SAFE_FIELDS},
    )
