from knowledge.models import Document
from projects.policies import authorized_documents
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Conversation


def get_conversation(membership, conversation_id):
    conversation = Conversation.objects.filter(
        pk=conversation_id, project=membership.project, user=membership.user
    ).first()
    if conversation is None:
        raise NotFound("Conversation not found.")
    validate_history(membership, conversation)
    return conversation


def validate_sources(membership, source_ids):
    ids = set(source_ids)
    allowed = set(authorized_documents(membership).filter(pk__in=ids).values_list("pk", flat=True))
    if ids != allowed:
        raise PermissionDenied("Access to a conversation source has changed. Start a new conversation.")
    # Reclassifications must also affect external routing of derived history.
    policies = Document.objects.filter(pk__in=allowed).values_list(
        "policy__classification", "knowledge_base__policy__classification"
    )
    return max((max(pair) for pair in policies), default=0)


def validate_history(membership, conversation):
    sources = set()
    classification = membership.project.default_classification
    for level, ids in conversation.messages.values_list("classification", "source_document_ids"):
        classification = max(classification, level)
        sources.update(ids)
    classification = max(classification, validate_sources(membership, sources))
    if classification > membership.clearance:
        raise PermissionDenied("Conversation exceeds your current clearance.")
    return sources, classification
