from django.conf import settings
from django.db import models
from projects.models import ProjectBoundModel


class Quota(ProjectBoundModel):
    """Mandatory project limit plus optional user, group, or provider limits."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    group = models.ForeignKey(
        "projects.ProjectGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="quotas"
    )
    provider = models.ForeignKey("providers.ProviderConfig", null=True, blank=True, on_delete=models.CASCADE)
    requests_per_minute = models.PositiveIntegerField(default=20)
    requests_per_day = models.PositiveIntegerField(default=500)
    tokens_per_day = models.PositiveIntegerField(default=500000)
    project_relations = ("group", "provider")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=True, group__isnull=True)
                    | models.Q(user__isnull=True, provider__isnull=True)
                    | models.Q(group__isnull=True, provider__isnull=True)
                ),
                name="quota_single_scope",
            ),
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(user__isnull=True, group__isnull=True, provider__isnull=True),
                name="quota_project",
            ),
            models.UniqueConstraint(
                fields=["project", "user"], condition=models.Q(user__isnull=False), name="quota_user"
            ),
            models.UniqueConstraint(
                fields=["project", "provider"],
                condition=models.Q(provider__isnull=False),
                name="quota_provider",
            ),
            models.UniqueConstraint(
                fields=["project", "group"],
                condition=models.Q(group__isnull=False),
                name="quota_group",
            ),
        ]

    def __str__(self):
        scope = self.user or self.group or self.provider or "project"
        return f"{self.project_id}/{scope}"


class UsageRecord(ProjectBoundModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.ForeignKey("providers.ProviderConfig", null=True, on_delete=models.SET_NULL)
    conversation = models.ForeignKey("chat.Conversation", null=True, on_delete=models.SET_NULL)
    groups = models.ManyToManyField("projects.ProjectGroup", blank=True, related_name="usage_records")
    status = models.CharField(
        max_length=20, default="reserved", choices=[(s, s) for s in ("reserved", "success", "failed")]
    )
    reserved_tokens = models.PositiveIntegerField()
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    project_relations = ("provider", "conversation")

    class Meta:
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["project", "user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.project_id}/{self.user_id}/{self.created_at:%Y-%m-%d %H:%M}"
