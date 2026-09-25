from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from chat.errors import QuotaExceeded
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from projects.models import Membership, Project, Tenant
from projects.policies import resolve_membership

from usage.models import Quota, UsageRecord
from usage.services import reserve


@skipUnless(connection.vendor == "postgresql", "PostgreSQL is required to test actual row locking")
class ConcurrentQuotaTests(TransactionTestCase):
    def test_two_workers_cannot_spend_one_remaining_request(self):
        user = get_user_model().objects.create_user("concurrent")
        tenant = Tenant.objects.create(name="Test", slug="test")
        project = Project.objects.create(tenant=tenant, name="Test", slug="test")
        Membership.objects.create(project=project, user=user)
        Quota.objects.create(project=project, requests_per_minute=1)
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                member = resolve_membership(actor, project.pk)
                barrier.wait(timeout=10)
                try:
                    reserve(member, 100)
                    return "accepted"
                except QuotaExceeded:
                    return "denied"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ["accepted", "denied"])
        self.assertEqual(UsageRecord.objects.count(), 1)
