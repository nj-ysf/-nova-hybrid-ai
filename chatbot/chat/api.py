from audit.services import record
from django.db import transaction
from knowledge.models import KnowledgeBase
from knowledge.services import ingest
from projects.models import Project, Role
from projects.policies import authorized_bases, resolve_membership
from projects.serializers import DocumentUploadSerializer, KnowledgeBaseSerializer, ProjectSerializer
from providers.base import ProviderError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import ServiceUnavailable
from .history import get_conversation
from .models import Conversation
from .serializers import ChatRequestSerializer, ConversationSerializer, MessageSerializer
from .services.orchestration import chat


class BoundedPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 100


def project_parameter(request):
    value = request.query_params.get("project_id")
    try:
        project_id = int(value)
        if project_id < 1:
            raise ValueError
        return project_id
    except (TypeError, ValueError):
        raise ValidationError({"project_id": "A positive project_id query parameter is required."}) from None


class ChatView(APIView):
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.audit_project_id = serializer.validated_data["project_id"]
        return Response(chat(request.user, **serializer.validated_data))


class ProjectViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    serializer_class = ProjectSerializer
    pagination_class = BoundedPagination
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Project.objects.filter(
            memberships__user=self.request.user, memberships__active=True, enabled=True
        ).order_by("id")

    def perform_update(self, serializer):
        member = resolve_membership(self.request.user, self.get_object().pk, Role.ADMIN)
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=member.project_id)
            serializer.save()
            record("project_changed", project=member.project, user=self.request.user)


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    pagination_class = BoundedPagination

    def get_queryset(self):
        qs = Conversation.objects.filter(
            user=self.request.user,
            project__enabled=True,
            project__memberships__user=self.request.user,
            project__memberships__active=True,
        )
        if "project_id" in self.request.query_params:
            project_id = project_parameter(self.request)
            resolve_membership(self.request.user, project_id)
            qs = qs.filter(project_id=project_id)
        return qs

    def get_object(self):
        conversation = super().get_object()
        member = resolve_membership(self.request.user, conversation.project_id)
        return get_conversation(member, conversation.pk)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        page = self.paginate_queryset(conversation.messages.all())
        return self.get_paginated_response(MessageSerializer(page, many=True).data)


class KnowledgeBaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = KnowledgeBaseSerializer
    pagination_class = BoundedPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def member(self, role=Role.READER):
        if "pk" in self.kwargs:
            project_id = (
                KnowledgeBase.objects.filter(pk=self.kwargs["pk"])
                .values_list("project_id", flat=True)
                .first()
            )
            if project_id is None:
                raise NotFound()
        else:
            project_id = project_parameter(self.request)
        return resolve_membership(self.request.user, project_id, role)

    def get_queryset(self):
        return authorized_bases(self.member()).order_by("pk")

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "membership": self.member(
                Role.EDITOR if self.request.method in ("POST", "PATCH") else Role.READER
            ),
        }

    def perform_create(self, serializer):
        serializer.save()
        record(
            "knowledge_base_created",
            project=serializer.instance.project,
            user=self.request.user,
            metadata={"knowledge_base_ids": [serializer.instance.pk]},
        )

    def perform_update(self, serializer):
        serializer.save()
        record(
            "knowledge_base_changed",
            project=serializer.instance.project,
            user=self.request.user,
            metadata={"knowledge_base_ids": [serializer.instance.pk]},
        )

    @action(detail=True, methods=["post"])
    def documents(self, request, pk=None):
        member = self.member(Role.EDITOR)
        self.get_object()
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = ingest(member, int(pk), **serializer.validated_data)
        except ProviderError:
            record("embedding_error", project=member.project, user=request.user)
            raise ServiceUnavailable("Local embedding service is unavailable.") from None
        return Response(
            {"id": document.pk, "title": document.title, "chunks": document.chunks.count()},
            status=status.HTTP_201_CREATED,
        )


class ConfigurationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = BoundedPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def member(self):
        return resolve_membership(self.request.user, self.kwargs["project_id"], Role.ADMIN)

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(project=self.member().project).order_by("pk")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.member()}

    def save_configuration(self, serializer):
        member = self.member()
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=member.project_id)
            serializer.save()
            record(
                "configuration_changed",
                project=member.project,
                user=self.request.user,
                metadata={"reason": self.serializer_class.Meta.model._meta.model_name},
            )

    perform_create = save_configuration
    perform_update = save_configuration
