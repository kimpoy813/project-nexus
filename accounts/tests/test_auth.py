"""
Authentication tests: login, logout, registration gating, and email verification.

These cover the paths that lock people out of the system if they break, and
the site-wide switches (registration disabled, maintenance mode) that are
controlled from the admin dashboard.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile, SiteConfiguration

from . import factories


User = get_user_model()


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = factories.make_user("auth_user", Profile.ROLE_FACULTY)

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("login"),
            {"username": "auth_user", "password": factories.DEFAULT_PASSWORD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_password_does_not_log_the_user_in(self):
        self.client.post(
            reverse("login"),
            {"username": "auth_user", "password": "wrong-password"},
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_username_does_not_log_anyone_in(self):
        self.client.post(
            reverse("login"),
            {"username": "does-not-exist", "password": factories.DEFAULT_PASSWORD},
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_clears_the_session(self):
        client = factories.make_client(self.user)
        self.assertIn("_auth_user_id", client.session)

        client.get(reverse("logout"))
        self.assertNotIn("_auth_user_id", client.session)


class RegistrationGatingTests(TestCase):
    """Registration can be switched off site-wide from the admin dashboard."""

    def setUp(self):
        self.config = SiteConfiguration.get_solo()

    def test_registration_page_is_available_when_enabled(self):
        self.config.registration_enabled = True
        self.config.save()

        self.assertEqual(self.client.get(reverse("register")).status_code, 200)

    def test_registration_redirects_when_disabled(self):
        self.config.registration_enabled = False
        self.config.save()

        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 302)

    def test_no_account_is_created_while_registration_is_disabled(self):
        self.config.registration_enabled = False
        self.config.save()

        before = User.objects.count()
        self.client.post(
            reverse("register"),
            {
                "username": "sneaky",
                "email": "sneaky@example.com",
                "password1": "A-str0ng-pass!",
                "password2": "A-str0ng-pass!",
            },
        )
        self.assertEqual(User.objects.count(), before)


class EmailVerificationTests(TestCase):
    def test_a_malformed_verification_link_is_rejected_gracefully(self):
        response = self.client.get(
            reverse("verify_email", kwargs={"uidb64": "bogus", "token": "bogus-token"})
        )
        # Should redirect or render an error page, never raise.
        self.assertIn(response.status_code, (200, 302, 404))

    def test_new_profiles_start_unverified(self):
        user = User.objects.create_user("fresh", "fresh@example.com", "pw-12345")
        self.assertFalse(user.profile.email_verified)


class MaintenanceModeTests(TestCase):
    """Maintenance mode locks the site for everyone except admins."""

    def setUp(self):
        self.config = SiteConfiguration.get_solo()
        self.config.maintenance_mode = True
        self.config.save()

    def tearDown(self):
        self.config.maintenance_mode = False
        self.config.save()

    def test_visitors_see_the_maintenance_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)

    def test_login_stays_reachable_during_maintenance(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_admins_can_still_use_the_site(self):
        admin = factories.make_user("maint_admin", Profile.ROLE_ADMIN)
        client = factories.make_client(admin)

        self.assertEqual(client.get("/").status_code, 200)

    def test_non_admins_are_locked_out(self):
        faculty = factories.make_user("maint_faculty", Profile.ROLE_FACULTY)
        client = factories.make_client(faculty)

        self.assertEqual(client.get("/").status_code, 503)


class ProfileSignalTests(TestCase):
    def test_a_profile_is_created_automatically_for_every_new_user(self):
        user = User.objects.create_user("signal_user", "s@example.com", "pw-12345")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_new_users_default_to_the_faculty_role(self):
        user = User.objects.create_user("signal_role", "sr@example.com", "pw-12345")
        self.assertEqual(user.profile.role, Profile.ROLE_FACULTY)
