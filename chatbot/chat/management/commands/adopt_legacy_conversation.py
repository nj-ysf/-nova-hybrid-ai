from audit.services import record
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from projects.models import Membership

from chat.models import Conversation


class Command(BaseCommand):
    help = "Explicitly assign ONE verified ownerless legacy conversation. Requires operator database access."

    def add_arguments(self, parser):
        parser.add_argument("--conversation", type=int, required=True)
        parser.add_argument("--project", type=int, required=True)
        parser.add_argument("--username", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        member = (
            Membership.objects.select_related("project")
            .filter(user=user, project_id=options["project"], active=True, clearance=3)
            .first()
        )
        conversation = (
            Conversation.objects.select_for_update()
            .filter(pk=options["conversation"], user=None, project=None)
            .first()
        )
        if member is None or conversation is None:
            raise CommandError(
                "Requires an unassigned conversation and an active member with restricted clearance (3)."
            )
        conversation.user = user
        conversation.project = member.project
        conversation.title = "Imported legacy conversation"
        conversation.save(update_fields=["user", "project", "title"])
        record(
            "legacy_adopted", project=member.project, user=user, metadata={"conversation_id": conversation.pk}
        )
        self.stdout.write(
            self.style.SUCCESS("Legacy conversation assigned; its messages retain restricted classification.")
        )
