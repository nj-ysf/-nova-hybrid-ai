from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "No permitted model is currently available."
    default_code = "provider_unavailable"


class QuotaExceeded(APIException):
    status_code = 429
    default_detail = "Usage limit reached. Try again later or contact a project administrator."
    default_code = "quota_exceeded"


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and response.status_code in (401, 403, 404, 429):
        from audit.services import record
        from projects.models import Membership

        request = context.get("request")
        user = getattr(request, "user", None)
        project = None
        project_id = getattr(context.get("view"), "kwargs", {}).get("project_id")
        if project_id is None:
            project_id = getattr(request, "audit_project_id", None)
        if getattr(user, "is_authenticated", False) and str(project_id).isdigit():
            membership = (
                Membership.objects.select_related("project")
                .filter(
                    user=user,
                    project_id=project_id,
                    active=True,
                )
                .first()
            )
            project = membership.project if membership else None
        record(
            "quota_denied" if response.status_code == 429 else "access_denied",
            project=project,
            user=user,
            metadata={"status": response.status_code},
        )
    if response is not None and response.status_code == 429:
        response["Retry-After"] = "60"
    return response
