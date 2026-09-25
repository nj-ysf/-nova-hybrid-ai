import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from knowledge.models import KnowledgeBase
from usage.models import Quota

from ...models import AccessPolicy, Classification, Membership, Project, ProjectGroup, Role, Tenant


class Command(BaseCommand):
    help = "Create idempotent local test users, profiles, groups, policies, knowledge bases, and quotas."

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int)
        parser.add_argument("--prefix", default="test")
        parser.add_argument("--password-env", default="DJANGO_TEST_USER_PASSWORD")
        parser.add_argument("--reset-passwords", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Test access seeding is available only with DJANGO_DEBUG=true.")
        password = os.getenv(options["password_env"], "")
        if len(password) < 12:
            raise CommandError(
                f"Set {options['password_env']} to a local test password of at least 12 characters."
            )
        if options["project_id"]:
            project = Project.objects.filter(pk=options["project_id"], enabled=True).first()
            if project is None:
                raise CommandError("Enabled project not found.")
        else:
            tenant, _ = Tenant.objects.get_or_create(slug="demo", defaults={"name": "Demo organization"})
            project, _ = Project.objects.get_or_create(
                tenant=tenant, slug="demo", defaults={"name": "Demo project"}
            )

        prefix = options["prefix"].strip().lower()
        if not prefix or len(prefix) > 30:
            raise CommandError("Prefix must contain 1 to 30 characters.")
        readers, _ = ProjectGroup.objects.get_or_create(project=project, name="Test local readers")
        editors, _ = ProjectGroup.objects.get_or_create(project=project, name="Test local editors")

        specs = (
            ("admin", Role.ADMIN, 3, True, editors, True),
            ("editor", Role.EDITOR, 2, False, editors, False),
            ("reader", Role.READER, 1, False, readers, False),
        )
        usernames = []
        for suffix, role, clearance, external, group, superuser in specs:
            username = f"{prefix}-{suffix}"
            user, created = get_user_model().objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.invalid",
                    "first_name": "Test",
                    "last_name": suffix.title(),
                },
            )
            if created or options["reset_passwords"]:
                user.set_password(password)
            user.is_active = True
            if superuser:
                user.is_staff = True
                user.is_superuser = True
            user.save()
            membership, _ = Membership.objects.update_or_create(
                project=project,
                user=user,
                defaults={
                    "role": role,
                    "clearance": clearance,
                    "can_use_external": external,
                    "active": True,
                },
            )
            membership.groups.set([group])
            usernames.append(username)

        shared_policy, _ = AccessPolicy.objects.update_or_create(
            project=project,
            name="Test shared local data",
            defaults={
                "minimum_role": Role.READER,
                "access_level": 0,
                "classification": Classification.INTERNAL,
            },
        )
        shared_policy.groups.set([readers, editors])
        editor_policy, _ = AccessPolicy.objects.update_or_create(
            project=project,
            name="Test editor local data",
            defaults={
                "minimum_role": Role.EDITOR,
                "access_level": 1,
                "classification": Classification.CONFIDENTIAL,
            },
        )
        editor_policy.groups.set([editors])
        KnowledgeBase.objects.update_or_create(
            project=project, name="Test shared data", defaults={"policy": shared_policy}
        )
        KnowledgeBase.objects.update_or_create(
            project=project, name="Test editor data", defaults={"policy": editor_policy}
        )
        Quota.objects.get_or_create(project=project, user=None, group=None, provider=None)
        Quota.objects.update_or_create(
            project=project,
            group=readers,
            defaults={
                "requests_per_minute": 10,
                "requests_per_day": 100,
                "tokens_per_day": 75000,
            },
        )
        Quota.objects.update_or_create(
            project=project,
            group=editors,
            defaults={
                "requests_per_minute": 20,
                "requests_per_day": 250,
                "tokens_per_day": 200000,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Test access ready for project {project.pk}: {', '.join(usernames)}. "
                "Passwords were read from the environment and were not printed."
            )
        )
