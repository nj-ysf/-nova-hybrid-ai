from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def index(request):
    if settings.FRONTEND_URL:
        return redirect(settings.FRONTEND_URL)
    return render(request, "chat/index.html")
