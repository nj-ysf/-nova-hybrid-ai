from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from knowledge.models import KnowledgeBase
from providers.models import AgentConfig, ModelConfig, ProviderConfig
from usage.models import Quota

from projects.models import AccessPolicy, Membership, Project, Role, Tenant


class Command(BaseCommand):
    help = (
        "Create an idempotent local-only demo project for an existing user. No passwords or provider calls."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--model", default="qwen2.5:0.5b")

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        if user is None:
            raise CommandError("Create the user first with createsuperuser or the operator admin.")
        tenant, _ = Tenant.objects.get_or_create(slug="demo", defaults={"name": "Demo organization"})
        project, _ = Project.objects.get_or_create(
            tenant=tenant, slug="demo", defaults={"name": "Demo project"}
        )
        Membership.objects.get_or_create(
            project=project, user=user, defaults={"role": Role.ADMIN, "clearance": 3}
        )
        provider, _ = ProviderConfig.objects.get_or_create(
            project=project, name="ollama", defaults={"connection_alias": "local"}
        )
        model, _ = ModelConfig.objects.get_or_create(
            project=project,
            provider=provider,
            name=options["model"],
            defaults={"context_tokens": 4096, "max_output_tokens": 256},
        )
        AgentConfig.objects.get_or_create(
            project=project, defaults={"primary_model": model, "rag_enabled": False}
        )
        policy, _ = AccessPolicy.objects.get_or_create(
            project=project, name="Project members", defaults={"classification": 1}
        )
        base, _ = KnowledgeBase.objects.get_or_create(
            project=project, name="Project handbook", defaults={"policy": policy}
        )
        Quota.objects.get_or_create(project=project, user=None, group=None, provider=None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo ready: project_id={project.pk}, knowledge_base_id={base.pk}, policy_id={policy.pk}"
            )
        )
