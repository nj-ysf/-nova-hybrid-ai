from django.urls import include, path
from projects.serializers import (
    AgentSerializer,
    GroupSerializer,
    MembershipSerializer,
    ModelSerializer,
    PolicySerializer,
    ProviderSerializer,
    QuotaSerializer,
)
from rest_framework.routers import SimpleRouter

from .api import ChatView, ConfigurationViewSet, ConversationViewSet, KnowledgeBaseViewSet, ProjectViewSet

router = SimpleRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("knowledge-bases", KnowledgeBaseViewSet, basename="knowledge-base")

urlpatterns = [path("chat/", ChatView.as_view()), path("", include(router.urls))]
for name, serializer in {
    "providers": ProviderSerializer,
    "models": ModelSerializer,
    "agents": AgentSerializer,
    "profiles": MembershipSerializer,
    "memberships": MembershipSerializer,
    "groups": GroupSerializer,
    "policies": PolicySerializer,
    "quotas": QuotaSerializer,
}.items():
    view = type(f"{name.title()}ViewSet", (ConfigurationViewSet,), {"serializer_class": serializer})
    urlpatterns.extend(
        [
            path(f"projects/<int:project_id>/{name}/", view.as_view({"get": "list", "post": "create"})),
            path(
                f"projects/<int:project_id>/{name}/<int:pk>/",
                view.as_view({"get": "retrieve", "patch": "partial_update"}),
            ),
        ]
    )
