"""
Tests for error handling and logging.

The codebase had ~70 broad ``except Exception`` handlers, many of which
discarded the error entirely — a database failure was indistinguishable from
"this user has no permissions", and nothing reached the logs because no
``LOGGING`` configuration existed.

These tests assert the two properties that matter:

1. Code that must not crash (context processors, middleware) still degrades
   gracefully when its dependencies fail.
2. When it does degrade, it *says so* in the log rather than failing silently.
"""

import logging
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from accounts.context_processors import site_configuration
from accounts.models import Profile

from . import factories


class LoggingConfigurationTests(SimpleTestCase):
    def test_logging_is_configured(self):
        self.assertTrue(settings.LOGGING, "no LOGGING configuration is defined")

    def test_application_loggers_are_declared(self):
        loggers = settings.LOGGING.get("loggers", {})
        for name in ["accounts", "proposals", "details", "django.request"]:
            with self.subTest(logger=name):
                self.assertIn(name, loggers)

    def test_a_console_handler_exists(self):
        self.assertIn("console", settings.LOGGING.get("handlers", {}))


class ContextProcessorResilienceTests(TestCase):
    """The context processor runs on every render, including error pages."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, user=None):
        request = self.factory.get("/")
        request.user = user or factories.make_user("cp_user", Profile.ROLE_FACULTY)
        return request

    def test_it_returns_all_expected_keys(self):
        context = site_configuration(self._request())
        for key in [
            "site_control",
            "role_capabilities",
            "can_submit_accomplishment",
            "can_view_accomplishment",
        ]:
            with self.subTest(key=key):
                self.assertIn(key, context)

    def test_a_database_failure_degrades_instead_of_raising(self):
        with patch(
            "accounts.models.SiteConfiguration.get_solo",
            side_effect=DatabaseError("connection lost"),
        ):
            context = site_configuration(self._request())

        self.assertIsNone(context["site_control"])

    def test_a_database_failure_is_logged(self):
        """The bug this replaces: the error vanished with no trace."""
        with patch(
            "accounts.models.SiteConfiguration.get_solo",
            side_effect=DatabaseError("connection lost"),
        ):
            with self.assertLogs("accounts.context_processors", level="WARNING") as logs:
                site_configuration(self._request())

        self.assertTrue(
            any("SiteConfiguration" in message for message in logs.output),
            f"expected a SiteConfiguration warning, got: {logs.output}",
        )

    def test_a_capability_lookup_failure_is_logged_and_degrades(self):
        request = self._request()

        with patch(
            "details.models.RoleCapability.objects.filter",
            side_effect=DatabaseError("table missing"),
        ):
            with self.assertLogs("accounts.context_processors", level="WARNING") as logs:
                context = site_configuration(request)

        self.assertEqual(context["role_capabilities"], set())
        self.assertTrue(logs.output)

    def test_an_anonymous_request_yields_no_capabilities(self):
        from django.contrib.auth.models import AnonymousUser

        context = site_configuration(self._request(user=AnonymousUser()))

        self.assertEqual(context["role_capabilities"], set())
        self.assertFalse(context["can_submit_accomplishment"])
        self.assertFalse(context["can_view_accomplishment"])


class MaintenanceMiddlewareResilienceTests(TestCase):
    def test_the_site_stays_up_when_the_config_cannot_be_read(self):
        """Failing open is deliberate: a config read error must not lock everyone out."""
        with patch(
            "accounts.models.SiteConfiguration.get_solo",
            side_effect=DatabaseError("connection lost"),
        ):
            with self.assertLogs("accounts.middleware", level="WARNING"):
                response = self.client.get("/")

        self.assertEqual(response.status_code, 200)


class UserFacingErrorTests(TestCase):
    """Internal exception text must not leak into the UI."""

    def test_role_update_failure_shows_a_generic_message(self):
        admin = factories.make_user("eh_admin", Profile.ROLE_ADMIN)
        target = factories.make_user("eh_target", Profile.ROLE_FACULTY)
        client = factories.make_client(admin)

        with patch(
            "accounts.models.Profile.save",
            side_effect=DatabaseError("constraint xyz_pkey violated"),
        ):
            with self.assertLogs("accounts.views.admin_users", level="ERROR"):
                response = client.post(
                    reverse("manage_roles"),
                    {"user_id": target.id, "role": Profile.ROLE_STAFF},
                    follow=True,
                )

        content = response.content.decode()
        self.assertNotIn("constraint xyz_pkey", content)
        self.assertIn("The error has been logged", content)


class NoBareExceptTests(SimpleTestCase):
    """A bare ``except:`` also catches KeyboardInterrupt and SystemExit."""

    def test_no_bare_except_clauses_in_application_code(self):
        import ast
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        offenders = []

        for app in ["accounts", "proposals", "details", "conf"]:
            for path in (root / app).rglob("*.py"):
                if "migrations" in path.parts:
                    continue
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        offenders.append(f"{path.relative_to(root)}:{node.lineno}")

        self.assertEqual(offenders, [], f"bare except clauses found: {offenders}")
