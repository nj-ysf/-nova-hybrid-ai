from django.core.exceptions import ValidationError as DjangoValidationError
from knowledge.models import KnowledgeBase
from providers.models import AgentConfig, ModelConfig, ProviderConfig
from rest_framework import serializers
from usage.models import Quota

from .models import AccessPolicy, Membership, Project, ProjectGroup
from .policies import authorized_policies


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "tenant_id",
            "name",
            "slug",
            "enabled",
            "allow_external",
            "external_max_classification",
            "default_classification",
        ]
        read_only_fields = ["id", "tenant_id", "slug"]


class ScopedSerializer(serializers.ModelSerializer):
    """Writable related fields only resolve inside the URL's project."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        membership = self.context.get("membership")
        if not membership:
            return
        for field in self.fields.values():
            related = getattr(field, "child_relation", field)
            queryset = getattr(related, "queryset", None)
            if queryset is not None and any(f.name == "project" for f in queryset.model._meta.fields):
                related.queryset = queryset.filter(project_id=membership.project_id)

    def validate(self, attrs):
        membership = self.context["membership"]
        if set(self.initial_data) - set(self.fields):
            raise serializers.ValidationError("Unknown configuration fields.")
        attrs["project"] = membership.project
        relations = [f.name for f in self.Meta.model._meta.many_to_many]
        values = {key: value for key, value in attrs.items() if key not in relations}
        instance = self.Meta.model()
        if self.instance:
            for field in self.Meta.model._meta.concrete_fields:
                setattr(instance, field.attname, getattr(self.instance, field.attname))
            instance._state.adding = False
        for key, value in values.items():
            setattr(instance, key, value)
        try:
            instance.full_clean(exclude=relations)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from None
        return attrs


class MembershipSerializer(ScopedSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, membership):
        return membership.user.get_full_name() or membership.user.get_username()

    class Meta:
        model = Membership
        fields = [
            "id",
            "user",
            "username",
            "display_name",
            "role",
            "clearance",
            "groups",
            "can_use_external",
            "active",
        ]
        validators = []


class GroupSerializer(ScopedSerializer):
    class Meta:
        model = ProjectGroup
        fields = ["id", "name"]
        validators = []


class PolicySerializer(ScopedSerializer):
    class Meta:
        model = AccessPolicy
        fields = ["id", "name", "minimum_role", "access_level", "classification", "groups"]


class ProviderSerializer(ScopedSerializer):
    class Meta:
        model = ProviderConfig
        fields = ["id", "name", "connection_alias", "enabled", "available"]
        validators = []


class ModelSerializer(ScopedSerializer):
    class Meta:
        model = ModelConfig
        fields = [
            "id",
            "provider",
            "name",
            "enabled",
            "context_tokens",
            "max_output_tokens",
            "supports_streaming",
        ]
        validators = []


class AgentSerializer(ScopedSerializer):
    system_prompt = serializers.CharField(max_length=8000)

    class Meta:
        model = AgentConfig
        fields = [
            "id",
            "primary_model",
            "fallback_model",
            "system_prompt",
            "rag_enabled",
            "top_k",
            "max_context_chars",
        ]
        validators = []


class QuotaSerializer(ScopedSerializer):
    class Meta:
        model = Quota
        fields = [
            "id",
            "user",
            "group",
            "provider",
            "requests_per_minute",
            "requests_per_day",
            "tokens_per_day",
        ]
        validators = []

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = attrs.get("user", getattr(self.instance, "user", None))
        if user and not Membership.objects.filter(project=attrs["project"], user=user, active=True).exists():
            raise serializers.ValidationError({"user": "An active project member is required."})
        return attrs


class KnowledgeBaseSerializer(ScopedSerializer):
    class Meta:
        model = KnowledgeBase
        fields = ["id", "name", "policy"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        policy = attrs.get("policy", getattr(self.instance, "policy", None))
        if policy and not authorized_policies(self.context["membership"]).filter(pk=policy.pk).exists():
            raise serializers.ValidationError({"policy": "Policy unavailable."})
        return attrs


class DocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    text = serializers.CharField(max_length=200000, trim_whitespace=False)
    policy_id = serializers.IntegerField(min_value=1)
