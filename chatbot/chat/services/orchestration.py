from audit.services import record
from django.db import transaction
from django.utils import timezone
from projects.policies import authorized_bases, resolve_membership
from providers.auto_router import choose_auto_route
from providers.base import ProviderError, Turn
from providers.models import AgentConfig
from providers.registry import connection_for, create_provider
from providers.router import candidates, evaluate, prioritize
from rest_framework.exceptions import PermissionDenied, ValidationError
from usage.services import assign_provider, finish, reserve

from ..agents import RAGAgent
from ..errors import QuotaExceeded, ServiceUnavailable
from ..history import get_conversation, validate_history, validate_sources
from ..models import ChatMessage, Conversation


def chat(
    user, *, project_id, message, conversation_id=None, mode="auto", classification=0, knowledge_base_ids=None
):
    membership = resolve_membership(user, project_id)
    project = membership.project
    classification = max(classification, project.default_classification)
    if classification > membership.clearance:
        raise PermissionDenied("Request exceeds your clearance.")
    if knowledge_base_ids is not None:
        allowed = set(
            authorized_bases(membership).filter(pk__in=knowledge_base_ids).values_list("pk", flat=True)
        )
        if set(knowledge_base_ids) != allowed:
            raise PermissionDenied("Knowledge base unavailable.")
    conversation = get_conversation(membership, conversation_id) if conversation_id else None
    sources, history_classification = (
        validate_history(membership, conversation) if conversation else (set(), 0)
    )
    classification = max(classification, history_classification)
    config = (
        AgentConfig.objects.select_related("primary_model__provider", "fallback_model__provider")
        .filter(project=project)
        .first()
    )
    if config is None:
        raise ServiceUnavailable("Project has no agent configuration.")
    decisions = candidates(config, membership, classification, mode)
    if not any(decision.allowed for decision in decisions):
        record("route_denied", project=project, user=user, metadata={"reason": "no_permitted_provider"})
        raise ServiceUnavailable()
    budget = max(decision.model.context_tokens for decision in decisions if decision.allowed)
    reservation = reserve(membership, budget, conversation)
    record("chat_request", project=project, user=user, metadata={"usage_id": reservation.pk})
    try:
        history = []
        if conversation:
            # Bound prompts; source lineage still covers the entire conversation.
            recent = list(conversation.messages.order_by("-id")[:20])
            history = [Turn(item.role, item.content) for item in reversed(recent)]
        agent = RAGAgent()
        prepared = agent.prepare(
            membership, config, message, history, sources, classification, knowledge_base_ids
        )
        record(
            "retrieval",
            project=project,
            user=user,
            metadata={
                "document_ids": sorted(prepared.source_ids),
                "chunk_ids": prepared.chunk_ids,
                "knowledge_base_ids": prepared.base_ids,
            },
        )
        routed_decisions = candidates(config, membership, prepared.classification, mode)
        if mode == "auto":
            allowed_modes = {
                connection_for(decision.model).get("mode")
                for decision in routed_decisions
                if decision.allowed
            }
            route = choose_auto_route(message, allowed_modes)
            routed_decisions = prioritize(routed_decisions, route.preferred_mode, local_only=route.local_only)
            record(
                "auto_route",
                project=project,
                user=user,
                metadata={"reason": route.reason},
            )
        saw_quota = False
        saw_oversize = False
        for decision in routed_decisions:
            model = decision.model
            if not decision.allowed:
                record(
                    "route_skipped",
                    project=project,
                    user=user,
                    metadata={"model_id": model.pk, "reason": decision.reason},
                )
                continue
            # Refresh model and membership before constructing the transport or charging its quota.
            membership = resolve_membership(user, project_id)
            prepared.classification = max(
                prepared.classification,
                membership.project.default_classification,
                validate_sources(membership, prepared.source_ids),
            )
            model.refresh_from_db()
            model.provider.refresh_from_db()
            current = evaluate(model, membership, prepared.classification, mode)
            if not current.allowed:
                continue
            try:
                provider = create_provider(model)
                tokens = provider.estimate_tokens(prepared.messages) + model.max_output_tokens
                if tokens > model.context_tokens:
                    saw_oversize = True
                    continue
                if reservation.status != "reserved":
                    reservation = reserve(membership, budget, conversation)
                assign_provider(reservation, model, tokens)
            except QuotaExceeded:
                saw_quota = True
                continue
            except ProviderError:
                continue
            # Refresh authorization immediately before dispatch; nothing from the model can alter it.
            membership = resolve_membership(user, project_id)
            prepared.classification = max(
                prepared.classification,
                membership.project.default_classification,
                validate_sources(membership, prepared.source_ids),
            )
            current = evaluate(model, membership, prepared.classification, mode)
            if not current.allowed:
                continue
            record(
                "provider_selected",
                project=project,
                user=user,
                metadata={"provider_id": model.provider_id, "model_id": model.pk, "reason": current.reason},
            )
            try:
                result = agent.execute(provider, prepared, model.max_output_tokens)
            except ProviderError:
                finish(reservation)
                record(
                    "provider_error", project=project, user=user, metadata={"provider_id": model.provider_id}
                )
                continue
            # Also recheck before delivering or persisting a response after a long model call.
            membership = resolve_membership(user, project_id)
            current_classification = max(
                prepared.classification, validate_sources(membership, prepared.source_ids)
            )
            if current_classification > membership.clearance:
                raise PermissionDenied("Access changed during generation.")
            with transaction.atomic():
                if conversation is None:
                    conversation = Conversation.objects.create(project=project, user=user)
                else:
                    Conversation.objects.select_for_update().get(pk=conversation.pk)
                metadata = {
                    "classification": current_classification,
                    "source_document_ids": sorted(prepared.source_ids),
                }
                ChatMessage.objects.create(
                    conversation=conversation, role="user", content=message, **metadata
                )
                ChatMessage.objects.create(
                    conversation=conversation, role="assistant", content=result.text, **metadata
                )
                Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())
                reservation.conversation = conversation
                reservation.save(update_fields=["conversation"])
                finish(reservation, result)
                record(
                    "chat_completed",
                    project=project,
                    user=user,
                    metadata={"conversation_id": conversation.pk, "provider_id": model.provider_id},
                )
            return {
                "reply": result.text,
                "conversation_id": conversation.pk,
                "provider": model.provider.name,
                "model": model.name,
                "sources": sorted(prepared.source_ids),
                "usage": {"input_tokens": result.input_tokens, "output_tokens": result.output_tokens},
            }
        if saw_quota:
            raise QuotaExceeded()
        if saw_oversize:
            raise ValidationError(
                "Conversation exceeds the configured context budget. Start a new conversation or use a larger model."
            )
        raise ServiceUnavailable()
    except ProviderError:
        raise ServiceUnavailable("Local embedding service is unavailable.") from None
    finally:
        if reservation.status == "reserved":
            finish(reservation)
