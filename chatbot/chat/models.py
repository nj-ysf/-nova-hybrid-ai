from django.conf import settings
from django.db import models
from projects.models import ProjectBoundModel


class Conversation(ProjectBoundModel):
    # Nullable only to quarantine existing ownerless conversations. APIs require both.
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=150, blank=True, default="New conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["project", "user", "-updated_at"])]

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    classification = models.PositiveSmallIntegerField(default=3)
    # IDs survive deletion: missing sources make history inaccessible.
    source_document_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
