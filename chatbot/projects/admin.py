from datetime import timedelta

from audit.models import AuditLog
from django.contrib import admin
from django.db.models import Case, Count, F, IntegerField, Q, Sum, When
from django.utils import timezone
from knowledge.models import Document, DocumentChunk, KnowledgeBase
from providers.models import AgentConfig, ModelConfig, ProviderConfig
from usage.models import Quota, UsageRecord

from .models import AccessPolicy, Membership, Project, ProjectGroup, Tenant


class OperatorAdmin(admin.ModelAdmin):
    """The admin site is an operator control plane, restricted to superusers."""

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class ReadOnlyOperatorAdmin(OperatorAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Tenant)
class TenantAdmin(OperatorAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Project)
class ProjectAdmin(OperatorAdmin):
    list_display = ("name", "tenant", "enabled", "allow_external", "default_classification")
    list_filter = ("enabled", "allow_external", "default_classification")
    search_fields = ("name", "slug", "tenant__name")
    list_select_related = ("tenant",)


@admin.register(Membership)
class MembershipAdmin(OperatorAdmin):
    list_display = ("user", "project", "role", "clearance", "can_use_external", "active")
    list_filter = ("project", "role", "clearance", "can_use_external", "active", "groups")
    search_fields = ("user__username", "user__first_name", "user__last_name", "project__name")
    list_select_related = ("user", "project")
    filter_horizontal = ("groups",)


@admin.register(ProjectGroup)
class ProjectGroupAdmin(OperatorAdmin):
    list_display = ("name", "project", "member_count")
    list_filter = ("project",)
    search_fields = ("name", "project__name")
    list_select_related = ("project",)

    @admin.display(description="Profiles")
    def member_count(self, group):
        return group.memberships.count()


@admin.register(AccessPolicy)
class AccessPolicyAdmin(OperatorAdmin):
    list_display = ("name", "project", "minimum_role", "access_level", "classification")
    list_filter = ("project", "minimum_role", "access_level", "classification", "groups")
    search_fields = ("name", "project__name")
    list_select_related = ("project",)
    filter_horizontal = ("groups",)


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(OperatorAdmin):
    list_display = ("name", "project", "policy")
    list_filter = ("project", "policy")
    search_fields = ("name", "project__name")
    list_select_related = ("project", "policy")


@admin.register(Document)
class DocumentAdmin(OperatorAdmin):
    list_display = ("title", "project", "knowledge_base", "policy", "created_at")
    list_filter = ("project", "knowledge_base", "policy", "created_at")
    search_fields = ("title",)
    list_select_related = ("project", "knowledge_base", "policy")
    readonly_fields = ("created_at", "embedding_model")

    def has_add_permission(self, request):
        # Ingestion must create text chunks and embeddings atomically.
        return False


@admin.register(DocumentChunk)
class DocumentChunkAdmin(ReadOnlyOperatorAdmin):
    list_display = ("document", "ordinal", "text_preview")
    search_fields = ("document__title", "text")
    list_select_related = ("document",)

    @admin.display(description="Text")
    def text_preview(self, chunk):
        return chunk.text[:120]


@admin.register(ProviderConfig)
class ProviderConfigAdmin(OperatorAdmin):
    list_display = ("name", "project", "connection_alias", "enabled", "available")
    list_filter = ("project", "enabled", "available", "connection_alias")
    search_fields = ("name", "project__name")


@admin.register(ModelConfig)
class ModelConfigAdmin(OperatorAdmin):
    list_display = ("name", "project", "provider", "enabled", "context_tokens", "max_output_tokens")
    list_filter = ("project", "provider", "enabled", "supports_streaming")
    search_fields = ("name",)


@admin.register(AgentConfig)
class AgentConfigAdmin(OperatorAdmin):
    list_display = ("project", "primary_model", "fallback_model", "rag_enabled", "top_k")
    list_filter = ("rag_enabled",)


def quota_records(quota):
    records = UsageRecord.objects.filter(project=quota.project)
    if quota.user_id:
        return records.filter(user=quota.user)
    if quota.group_id:
        return records.filter(groups=quota.group)
    if quota.provider_id:
        return records.filter(provider=quota.provider)
    return records


def quota_usage(quota):
    cached = getattr(quota, "_admin_usage", None)
    if cached is not None:
        return cached
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    records = quota_records(quota)
    cached = records.aggregate(
        minute=Count("pk", filter=Q(created_at__gte=now - timedelta(minutes=1))),
        day=Count("pk", filter=Q(created_at__gte=today)),
        tokens=Sum(
            Case(
                When(status="success", then=F("input_tokens") + F("output_tokens")),
                default=F("reserved_tokens"),
                output_field=IntegerField(),
            ),
            filter=Q(created_at__gte=today),
        ),
    )
    cached["tokens"] = cached["tokens"] or 0
    quota._admin_usage = cached
    return cached


@admin.register(Quota)
class QuotaAdmin(OperatorAdmin):
    list_display = ("project", "scope", "minute_usage", "daily_usage", "token_usage")
    list_filter = ("project", "group", "provider")
    search_fields = ("project__name", "user__username", "group__name", "provider__name")
    list_select_related = ("project", "user", "group", "provider")

    @admin.display(description="Scope")
    def scope(self, quota):
        if quota.user_id:
            return f"Profile: {quota.user}"
        if quota.group_id:
            return f"Group: {quota.group.name}"
        if quota.provider_id:
            return f"Provider: {quota.provider.name}"
        return "Whole project"

    @admin.display(description="Requests/min")
    def minute_usage(self, quota):
        return f"{quota_usage(quota)['minute']} / {quota.requests_per_minute}"

    @admin.display(description="Requests/day")
    def daily_usage(self, quota):
        return f"{quota_usage(quota)['day']} / {quota.requests_per_day}"

    @admin.display(description="Tokens/day")
    def token_usage(self, quota):
        return f"{quota_usage(quota)['tokens']} / {quota.tokens_per_day}"


@admin.register(UsageRecord)
class UsageRecordAdmin(ReadOnlyOperatorAdmin):
    list_display = (
        "created_at",
        "project",
        "user",
        "provider",
        "status",
        "reserved_tokens",
        "measured_tokens",
    )
    list_filter = ("project", "provider", "status", "groups", "created_at")
    search_fields = ("user__username", "project__name")
    list_select_related = ("project", "user", "provider")

    @admin.display(description="Input + output")
    def measured_tokens(self, usage):
        return usage.input_tokens + usage.output_tokens


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyOperatorAdmin):
    list_display = ("created_at", "event", "project", "user")
    list_filter = ("event", "project", "created_at")
    search_fields = ("event", "user__username")
