from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("otp/request/", views.OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("otp/login/", views.OTPLoginView.as_view(), name="auth-otp-login"),
    path("password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/reset/", views.PasswordResetRequestView.as_view(),
         name="auth-password-reset"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(),
         name="auth-password-reset-confirm"),
]