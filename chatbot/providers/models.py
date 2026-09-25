from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from projects.models import ProjectBoundModel


class ProviderConfig(ProjectBoundModel):
    name = models.SlugField()
    connection_alias = models.CharField(max_length=80)
    enabled = models.BooleanField(default=True)
    available = models.BooleanField(
        default=True, help_text="Administrative availability switch; failures are handled at execution."
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="provider_project_name")]

    def clean(self):
        super().clean()
        if self.connection_alias not in settings.LLM_CONNECTIONS:
            raise ValidationError({"connection_alias": "Unknown deployment connection."})

    def __str__(self):
        return f"{self.project_id}/{self.name}"


class ModelConfig(ProjectBoundModel):
    provider = models.ForeignKey(ProviderConfig, on_delete=models.CASCADE, related_name="models")
    name = models.CharField(max_length=150)
    enabled = models.BooleanField(default=True)
    context_tokens = models.PositiveIntegerField(
        default=8192, validators=[MinValueValidator(512), MaxValueValidator(131072)]
    )
    max_output_tokens = models.PositiveIntegerField(
        default=512, validators=[MinValueValidator(1), MaxValueValidator(8192)]
    )
    supports_streaming = models.BooleanField(default=True)
    project_relations = ("provider",)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "name"], name="model_provider_name")]

    def clean(self):
        super().clean()
        if self.max_output_tokens >= self.context_tokens:
            raise ValidationError({"max_output_tokens": "Must leave room for input within context_tokens."})
        if self.provider_id:
            connection = settings.LLM_CONNECTIONS.get(self.provider.connection_alias, {})
            if connection.get("mode") == "local" and ("cloud" in self.name.lower() or "://" in self.name):
                raise ValidationError({"name": "Local providers require an installed local model."})

    def __str__(self):
        return self.name


class AgentConfig(ProjectBoundModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="agent_config")
    primary_model = models.ForeignKey(ModelConfig, on_delete=models.PROTECT, related_name="primary_agents")
    fallback_model = models.ForeignKey(
        ModelConfig, null=True, blank=True, on_delete=models.SET_NULL, related_name="fallback_agents"
    )
    system_prompt = models.TextField(default="You are a helpful assistant.")
    rag_enabled = models.BooleanField(default=True)
    top_k = models.PositiveSmallIntegerField(
        default=4, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    max_context_chars = models.PositiveIntegerField(
        default=12000, validators=[MinValueValidator(100), MaxValueValidator(24000)]
    )
    project_relations = ("primary_model", "fallback_model")

    def __str__(self):
        return f"Agent for {self.project_id}"
