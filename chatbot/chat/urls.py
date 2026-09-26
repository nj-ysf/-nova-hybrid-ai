from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("csrf/", views.csrf_cookie, name="csrf_cookie"),
    path("login/", LoginView.as_view(template_name="chat/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
