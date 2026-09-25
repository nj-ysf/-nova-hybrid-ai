from datetime import timedelta

from chat.errors import QuotaExceeded
from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, Sum, When
from django.utils import timezone
from projects.models import Project

from .models import Quota, UsageRecord


def check_limit(quota, records, budget):
    now = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily = records.filter(created_at__gte=today)
    tokens = (
        daily.aggregate(
            total=Sum(
                Case(
                    When(status="success", then=F("input_tokens") + F("output_tokens")),
                    default=F("reserved_tokens"),
                    output_field=IntegerField(),
                )
            )
        )["total"]
        or 0
    )
    if (
        records.filter(created_at__gte=now - timedelta(minutes=1)).count() >= quota.requests_per_minute
        or daily.count() >= quota.requests_per_day
        or tokens + budget > quota.tokens_per_day
    ):
        raise QuotaExceeded()


def scoped_records(records, quota):
    if quota.user_id:
        return records.filter(user_id=quota.user_id)
    if quota.group_id:
        return records.filter(groups=quota.group_id)
    return records


def applicable_limits(project_id, user_id, group_ids):
    return (
        Quota.objects.filter(project_id=project_id, provider=None)
        .filter(
            Q(user=None, group=None) | Q(user_id=user_id, group=None) | Q(user=None, group_id__in=group_ids)
        )
        .distinct()
    )


@transaction.atomic
def reserve(membership, budget, conversation=None):
    # One stable project row serializes reservations even before a quota row exists.
    Project.objects.select_for_update().get(pk=membership.project_id)
    Quota.objects.get_or_create(project=membership.project, user=None, group=None, provider=None)
    group_ids = list(membership.groups.values_list("pk", flat=True))
    quotas = applicable_limits(membership.project_id, membership.user_id, group_ids)
    records = UsageRecord.objects.filter(project=membership.project)
    for quota in quotas:
        check_limit(quota, scoped_records(records, quota), budget)
    reservation = UsageRecord.objects.create(
        project=membership.project, user=membership.user, reserved_tokens=budget, conversation=conversation
    )
    reservation.groups.set(group_ids)
    return reservation


@transaction.atomic
def assign_provider(reservation, model, budget):
    Project.objects.select_for_update().get(pk=reservation.project_id)
    records = UsageRecord.objects.filter(project_id=reservation.project_id).exclude(pk=reservation.pk)
    group_ids = list(reservation.groups.values_list("pk", flat=True))
    # Recheck all scopes if an unattempted candidate is replaced with a larger request.
    for limit in applicable_limits(reservation.project_id, reservation.user_id, group_ids):
        check_limit(limit, scoped_records(records, limit), budget)
    quota = Quota.objects.filter(project_id=reservation.project_id, provider=model.provider).first()
    if quota:
        records = UsageRecord.objects.filter(
            project_id=reservation.project_id, provider=model.provider
        ).exclude(pk=reservation.pk)
        check_limit(quota, records, budget)
    reservation.provider = model.provider
    reservation.reserved_tokens = budget
    reservation.save(update_fields=["provider", "reserved_tokens"])


@transaction.atomic
def finish(reservation, result=None):
    Project.objects.select_for_update().get(pk=reservation.project_id)
    if result:
        reservation.status = "success"
        reservation.input_tokens = result.input_tokens
        reservation.output_tokens = result.output_tokens
    else:
        # A timed-out upstream call may still be billed; retain its reservation.
        reservation.status = "failed"
    reservation.save(update_fields=["status", "input_tokens", "output_tokens"])
