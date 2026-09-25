"""All retrieval predicates are constructed from server-resolved membership."""

from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import AccessPolicy, Membership, Role


def resolve_membership(user, project_id, minimum_role=Role.READER):
    membership = (
        Membership.objects.select_related("project", "project__tenant")
        .filter(
            user=user,
            user__is_active=True,
            active=True,
            project_id=project_id,
            project__enabled=True,
        )
        .first()
    )
    if membership is None:
        raise NotFound("Project not found.")
    if membership.role < minimum_role:
        raise PermissionDenied("Insufficient project role.")
    return membership


def policy_filter(membership, prefix="policy__"):
    groups = membership.groups.filter(project_id=membership.project_id).values("pk")
    return Q(
        **{
            f"{prefix}project_id": membership.project_id,
            f"{prefix}minimum_role__lte": membership.role,
            f"{prefix}access_level__lte": membership.clearance,
            f"{prefix}classification__lte": membership.clearance,
        }
    ) & (Q(**{f"{prefix}groups__isnull": True}) | Q(**{f"{prefix}groups__in": groups}))


def authorized_policies(membership):
    return AccessPolicy.objects.filter(policy_filter(membership, "")).distinct()


def authorized_bases(membership):
    from knowledge.models import KnowledgeBase

    return (
        KnowledgeBase.objects.filter(project_id=membership.project_id)
        .filter(policy_filter(membership))
        .distinct()
    )


def authorized_documents(membership):
    from knowledge.models import Document

    return (
        Document.objects.filter(
            project_id=membership.project_id,
            knowledge_base__project_id=membership.project_id,
            knowledge_base__project__tenant_id=membership.project.tenant_id,
        )
        .filter(policy_filter(membership), policy_filter(membership, "knowledge_base__policy__"))
        .distinct()
    )
