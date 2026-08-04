"""
Registration, login/logout, email verification, and profile self-service.
"""
import logging

from django.conf import settings
from django.db import DatabaseError
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.html import strip_tags
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.http import urlsafe_base64_decode
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from ..campus_data import get_college_choices
from ..campus_data import get_department_choices
from ..forms import ProfileUpdateForm
from ..forms import RegisterForm
from ..models import Profile
from ..models import SiteConfiguration
from ..tokens import email_verification_token

logger = logging.getLogger(__name__)
from .helpers import User, _get_client_ip, _get_or_create_profile, _get_role_dashboard_name, _increment_failed, _is_blocked, _normalize_role, _reset_failed


def get_colleges_ajax(request):
    campus = (request.GET.get("campus") or "").strip()
    colleges = [
        {"value": value, "label": label}
        for value, label in get_college_choices(campus)
    ]
    return JsonResponse({"colleges": colleges})


def get_departments_ajax(request):
    campus = (request.GET.get("campus") or "").strip()
    college = (request.GET.get("college") or "").strip()
    departments = [
        {"value": value, "label": label}
        for value, label in get_department_choices(campus, college)
    ]
    return JsonResponse({"departments": departments})


@require_http_methods(["GET", "POST"])
def register_view(request):
    try:
        site_config = SiteConfiguration.get_solo()
    except DatabaseError:
        logger.warning(
            "Could not load SiteConfiguration for the registration gate.", exc_info=True
        )
        site_config = None

    if site_config and not site_config.registration_enabled:
        messages.warning(request, "Public registration is currently disabled by the system administrator.")
        return redirect("login")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                username = form.cleaned_data.get("username")
                raw_password = (
                    form.cleaned_data.get("password")
                    or form.cleaned_data.get("password1")
                )
                full_name = form.cleaned_data.get("full_name") or username
                campus = form.cleaned_data.get("campus", "")
                college = form.cleaned_data.get("college", "")
                department = form.cleaned_data.get("department", "")

                with transaction.atomic():
                    user = form.save(commit=False)

                    if raw_password:
                        user.set_password(raw_password)

                    user.is_active = False
                    user.save()

                    Profile.objects.update_or_create(
                        user=user,
                        defaults={
                            "full_name": full_name,
                            "campus": campus,
                            "college": college,
                            "department": department,
                            "role": Profile.ROLE_FACULTY,
                        },
                    )

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = email_verification_token.make_token(user)
                verify_url = request.build_absolute_uri(
                    reverse("verify_email", kwargs={"uidb64": uid, "token": token})
                )

                subject = "Verify your NExUS account"
                html_message = render_to_string(
                    "accounts/email/verification_email.html",
                    {
                        "user": user,
                        "full_name": full_name,
                        "verify_url": verify_url,
                        "logo_url": request.build_absolute_uri(
                            static("images/extension-logo-128.png")
                        ),
                    },
                )
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        "Account created! Please check your email to verify your account.",
                    )
                except Exception:
                    logger.exception(
                        "Verification email failed for new account %r.", user.username
                    )
                    messages.warning(
                        request,
                        "Account created but verification email could not be sent. Please contact support.",
                    )

                return redirect("login")

            except Exception:
                logger.exception("Registration failed while creating the account.")
                messages.error(request, "An error occurred while creating the account. Please try again.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["GET"])
def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])

        profile, _ = _get_or_create_profile(user)
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])

        messages.success(request, "Email verified successfully! You may now log in.")
        return redirect("login")

    messages.error(request, "Invalid or expired verification link.")
    return redirect("register")


@require_http_methods(["GET", "POST"])
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    if request.method == "GET":
        get_token(request)

    if request.method == "GET" and request.GET.get("reason") == "idle":
        messages.warning(request, "You were logged out due to 10 minutes of inactivity.")

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        client_ip = _get_client_ip(request)

        identifiers = [client_ip]
        if identifier:
            identifiers.append(identifier.lower())

        for key in identifiers:
            if _is_blocked(key):
                messages.error(request, "Too many failed login attempts. Try again later.")
                return render(request, "accounts/login.html")

        username_to_auth = identifier
        if "@" in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                username_to_auth = user_obj.username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username_to_auth, password=password)

        if user:
            if not user.is_active:
                messages.error(request, "Email not verified. Please check your inbox.")
                return render(request, "accounts/login.html")

            for key in identifiers:
                _reset_failed(key)

            auth_login(request, user)
            messages.success(request, "Login successful!")

            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            profile, _ = _get_or_create_profile(request.user)
            role = _normalize_role(profile.role)
            return redirect(_get_role_dashboard_name(role))

        for key in identifiers:
            _increment_failed(key)

        messages.error(request, "Invalid username/email or password.")

    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("login")


@require_POST
@login_required
def logout_idle_view(request):
    auth_logout(request)
    return JsonResponse({"ok": True})


@login_required
def profile_view(request):
    profile, _ = _get_or_create_profile(request.user)
    return render(request, "accounts/profile.html", {"profile": profile})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    profile, _ = _get_or_create_profile(request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            updated_profile = form.save(commit=False)

            full_name = form.cleaned_data.get("full_name")
            if full_name is not None:
                updated_profile.full_name = full_name

            updated_profile.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile_view")
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(
        request,
        "accounts/profile_edit.html",
        {"form": form, "profile": profile},
    )


@login_required
def change_password_email_view(request):
    user_email = request.user.email

    if not user_email:
        messages.error(request, "No email address is linked to your account.")
        return redirect("profile_view")

    form = PasswordResetForm({"email": user_email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            email_template_name="accounts/password_reset_email.html",
            html_email_template_name="accounts/email/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        )
        return render(
            request,
            "accounts/change_password_email_sent.html",
            {"email": user_email},
        )

    messages.error(request, "Unable to send password reset email.")
    return redirect("profile_view")


@ensure_csrf_cookie
@csrf_protect
def debug_login_view(request):
    if request.method == "POST":
        return HttpResponseRedirect(reverse("login"))
    return render(request, "debug_login.html")
