import os
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from knowledge.models import KnowledgeBase
from usage.models import Quota, UsageRecord

from .admin import QuotaAdmin
from .models import Membership, Project, ProjectGroup, Tenant


@override_settings(DEBUG=True)
class TestAccessSeedTests(TestCase):
    def setUp(self):
        tenant = Tenant.objects.create(name="Test tenant", slug="test-tenant")
        self.project = Project.objects.create(tenant=tenant, name="Test project", slug="test-project")

    def seed(self):
        output = StringIO()
        with patch.dict(os.environ, {"DJANGO_TEST_USER_PASSWORD": "local-test-password-123"}):
            call_command("seed_test_access", project_id=self.project.pk, stdout=output)
        return output.getvalue()

    def test_command_creates_idempotent_users_access_and_limits(self):
        output = self.seed()
        self.seed()

        users = get_user_model().objects.filter(username__startswith="test-")
        self.assertEqual(users.count(), 3)
        platform_admin = users.get(username="test-admin")
        self.assertTrue(platform_admin.is_superuser)
        self.assertTrue(platform_admin.is_staff)
        self.assertTrue(platform_admin.check_password("local-test-password-123"))
        self.assertEqual(Membership.objects.filter(project=self.project).count(), 3)
        self.assertEqual(ProjectGroup.objects.filter(project=self.project).count(), 2)
        self.assertEqual(KnowledgeBase.objects.filter(project=self.project).count(), 2)
        self.assertEqual(Quota.objects.filter(project=self.project).count(), 3)
        self.assertNotIn("local-test-password-123", output)

    def test_demo_seed_is_idempotent_with_group_quotas(self):
        tenant = Tenant.objects.create(name="Demo organization", slug="demo")
        project = Project.objects.create(tenant=tenant, name="Demo project", slug="demo")
        with patch.dict(os.environ, {"DJANGO_TEST_USER_PASSWORD": "local-test-password-123"}):
            call_command("seed_test_access", project_id=project.pk, stdout=StringIO())

        call_command("seed_demo", username="test-admin", stdout=StringIO())
        call_command("seed_demo", username="test-admin", stdout=StringIO())

        project_quotas = Quota.objects.filter(project=project, user=None, group=None, provider=None)
        self.assertEqual(project_quotas.count(), 1)

    def test_admin_manages_users_access_and_shows_quota_usage(self):
        self.seed()
        platform_admin = get_user_model().objects.get(username="test-admin")
        self.client.force_login(platform_admin)
        self.assertEqual(self.client.get(reverse("admin:auth_user_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:projects_membership_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:usage_quota_changelist")).status_code, 200)

        request = RequestFactory().get("/admin/")
        request.user = platform_admin
        self.assertTrue(admin.site._registry[get_user_model()].has_delete_permission(request))
        self.assertTrue(admin.site._registry[Membership].has_delete_permission(request))
        self.assertFalse(admin.site._registry[UsageRecord].has_delete_permission(request))

        reader = get_user_model().objects.get(username="test-reader")
        group = ProjectGroup.objects.get(project=self.project, name="Test local readers")
        usage = UsageRecord.objects.create(
            project=self.project,
            user=reader,
            status="success",
            reserved_tokens=100,
            input_tokens=10,
            output_tokens=5,
        )
        usage.groups.add(group)
        quota = Quota.objects.get(project=self.project, group=group)
        quota_admin = QuotaAdmin(Quota, admin.site)
        self.assertEqual(quota_admin.minute_usage(quota), "1 / 10")
        self.assertEqual(quota_admin.daily_usage(quota), "1 / 100")
        self.assertEqual(quota_admin.token_usage(quota), "15 / 75000")
