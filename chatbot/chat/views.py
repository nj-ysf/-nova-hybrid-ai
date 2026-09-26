from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def csrf_cookie(request):
    return JsonResponse({"ok": True})


@login_required
def index(request):
    if settings.FRONTEND_URL:
        return redirect(settings.FRONTEND_URL)
    return render(request, "chat/index.html")
