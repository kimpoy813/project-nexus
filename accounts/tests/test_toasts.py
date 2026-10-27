"""
Feedback: one toast, on every screen.

Django's messages, the dashboards' AJAX handlers, the wizard's in-page swaps,
the maintenance page, the debug sign-in and Django's own admin all report
through a single helper — ``window.nexusToast(message, type)`` from
``templates/partials/_toaster.html``. These tests keep the three halves of that
promise:

  * every full page mounts the toaster (root + module + helper),
  * Django's messages reach the page in the shape the helper reads,
  * nothing reports through a native ``alert()`` any more.

The comment scan covers a real bug: ``{# ... #}`` is a *single-line* comment in
Django, so a comment spread over two lines is not stripped — it is printed
verbatim on the page (the nested step editor explained itself to every admin
who opened it, and base.html printed a note about ``.nexus-shell`` above the
content of every page in the system). ``{% comment %}`` is the multi-line form.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import SiteConfiguration

from . import factories


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FOLDERS = ("templates", "accounts/templates", "details/templates", "proposals/templates")

#: Built assets and third-party bundles are not ours to lint.
SKIPPED_DIRS = {".git", "node_modules", "staticfiles", "dist", "build"}


def _repo_templates():
    for folder in TEMPLATE_FOLDERS:
        for path in sorted((REPO_ROOT / folder).rglob("*.html")):
            if SKIPPED_DIRS.isdisjoint(path.parts):
                yield path


def _repo_scripts():
    """Everything that can raise user-facing feedback: page scripts and inline JS."""
    for path in sorted((REPO_ROOT / "static" / "js").glob("*.js")):
        yield path
    yield from _repo_templates()


def _multi_line_comments(path):
    """Yield ``(line number, text)`` for every ``{#`` that closes on another line.

    Django only treats ``{# ... #}`` as a comment when it opens and closes on
    the same line; anything longer is emitted as literal text.
    """
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"\{#", text):
        remainder = text[match.end():]
        closing = remainder.find("#}")
        body = remainder if closing == -1 else remainder[:closing]
        if "\n" in body:
            yield text[: match.start()].count("\n") + 1, body.strip().replace("\n", " ")[:70]


class TemplateSourceTests(SimpleTestCase):
    """Scans over the sources: they catch a leak on a page no test renders."""

    def test_no_template_comment_spans_two_lines(self):
        offenders = [
            f"{path.relative_to(REPO_ROOT)}:{line} ({body}...)"
            for path in _repo_templates()
            for line, body in _multi_line_comments(path)
        ]
        self.assertEqual(
            offenders,
            [],
            "a multi-line {# #} comment is rendered verbatim — use {% comment %}: "
            + "; ".join(offenders),
        )

    def test_no_screen_reports_through_a_native_alert(self):
        pattern = re.compile(r"(?<![\w.$])alert\s*\(")
        offenders = []
        for path in _repo_scripts():
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{text[: match.start()].count(chr(10)) + 1}")
        self.assertEqual(
            offenders,
            [],
            "use window.nexusToast(message, type) instead of alert(): " + "; ".join(offenders),
        )

    def test_the_toaster_partial_owns_the_mount_and_the_helper(self):
        partial = (REPO_ROOT / "templates" / "partials" / "_toaster.html").read_text(encoding="utf-8")
        self.assertIn('id="goey-toast-root"', partial)
        self.assertIn('id="toast-container"', partial)
        self.assertIn("goey/toaster.js", partial)
        self.assertIn("window.nexusToast =", partial)
        for tag in ("success", "error", "warning"):
            self.assertIn(f'indexOf("{tag}")', partial)

    def test_only_the_partial_defines_the_mount_point(self):
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in (REPO_ROOT / "templates").rglob("*.html")
            if 'id="goey-toast-root"' in path.read_text(encoding="utf-8")
            and "partials" not in path.parts
        ]
        self.assertEqual(offenders, [], "mount the toaster through the partial: " + ", ".join(offenders))

    def test_django_messages_are_rendered_only_by_the_shared_toaster(self):
        """Feature templates must not add their own inline copy of a flash message."""
        message_loop = re.compile(r"{%\s*for\s+message\s+in\s+messages\s*%}")
        shared_partial = REPO_ROOT / "templates" / "partials" / "_toaster.html"
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in _repo_templates()
            if path != shared_partial
            and message_loop.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(
            offenders,
            [],
            "render Django messages through partials/_toaster.html: " + ", ".join(offenders),
        )


class ToastMountTests(TestCase):
    """Every full page hands the browser the toaster and the helper."""

    def assertToasterMounted(self, response, *, context="", status=200):
        self.assertEqual(response.status_code, status, context)
        html = response.content.decode()
        self.assertEqual(html.count('id="goey-toast-root"'), 1, f"toaster root not mounted once {context}")
        self.assertIn("goey/toaster.js", html, f"toaster module missing {context}")
        self.assertIn("goey/toaster.css", html, f"toaster stylesheet missing {context}")
        self.assertIn("window.nexusToast", html, f"toast helper missing {context}")
        return html

    def test_public_and_auth_pages_mount_the_toaster(self):
        for url in ("/", reverse("login"), reverse("register"), reverse("password_reset")):
            with self.subTest(url=url):
                self.assertToasterMounted(self.client.get(url), context=f"on {url}")

    def test_workspace_pages_mount_the_toaster(self):
        user, client = factories.admin()
        for url in (
            reverse("admin_dashboard"),
            reverse("profile_view"),
            reverse("page_content_list"),
            reverse("processes_list"),
            reverse("wizard_steps_manager"),
        ):
            with self.subTest(url=url):
                self.assertToasterMounted(client.get(url), context=f"on {url}")

    def test_role_dashboards_mount_the_toaster(self):
        for factory in (factories.admin, factories.director, factories.staff,
                        factories.evaluator, factories.faculty):
            with self.subTest(role=factory.__name__):
                user, client = factory()
                self.assertToasterMounted(client.get("/dashboard/", follow=True),
                                          context=f"for {factory.__name__}")

    @override_settings(DEBUG=True)
    def test_the_debug_sign_in_mounts_the_toaster(self):
        self.assertToasterMounted(self.client.get(reverse("debug_login")))

    def test_the_debug_sign_in_is_absent_when_debug_is_off(self):
        """The CSRF diagnostics page must not be reachable on the live site."""
        self.assertEqual(self.client.get(reverse("debug_login")).status_code, 404)

    def test_the_maintenance_page_mounts_the_toaster(self):
        config = SiteConfiguration.get_solo()
        config.maintenance_mode = True
        config.save(update_fields=["maintenance_mode"])
        self.assertToasterMounted(self.client.get("/"), context="on the maintenance page", status=503)

    def test_djangos_own_admin_mounts_the_toaster(self):
        user, client = factories.admin()
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])
        html = self.assertToasterMounted(client.get("/admin/"), context="in the Django admin")
        # The admin's own list is removed only once the toaster has taken over.
        self.assertIn(".messagelist", html)


class MessageToToastTests(TestCase):
    """Django's messages arrive in the shape templates/partials/_toaster.html reads."""

    def test_a_login_error_is_rendered_as_toast_data(self):
        response = self.client.post(
            reverse("login"),
            {"username": "nobody@example.com", "password": "wrong-password"},
            follow=True,
        )
        html = response.content.decode()
        self.assertIn('id="messages-data"', html)
        self.assertIn('data-message="Invalid username/email or password."', html)
        self.assertIn('data-tags="error"', html)

    def test_a_successful_login_renders_a_success_toast(self):
        user = factories.make_user("t_toast_login")
        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": factories.DEFAULT_PASSWORD},
            follow=True,
        )
        html = response.content.decode()
        self.assertIn('id="messages-data"', html)
        self.assertIn('data-message="Login successful!"', html)
        self.assertIn('data-tags="success"', html)


class DjangoAdminToastTests(TestCase):
    """The admin's own messages ride the same rail."""

    def setUp(self):
        user, self.client = factories.admin()
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])

    def test_an_admin_message_becomes_toast_data(self):
        response = self.client.post(
            "/admin/auth/group/add/",
            {"name": "Toast Testers"},
            follow=True,
        )
        html = response.content.decode()
        self.assertIn('id="messages-data"', html)
        self.assertIn("was added successfully", html)
        # The list the admin ships with stays in the markup for the case where
        # the toaster never loads; a script removes it once the toasts are up.
        self.assertIn(".messagelist", html)


class DashboardFeedbackTests(TestCase):
    """The dashboards talk to the user through the helper, not through alert()."""

    def test_dashboards_report_through_the_toast_helper(self):
        for factory in (factories.admin, factories.faculty, factories.evaluator, factories.staff):
            with self.subTest(role=factory.__name__):
                user, client = factory()
                html = client.get("/dashboard/", follow=True).content.decode()
                self.assertNotIn("alert(", html, f"{factory.__name__} still uses a native alert")
                self.assertIn("window.nexusToast", html)

    def test_the_process_editor_does_not_print_its_own_comment(self):
        user, client = factories.admin()
        html = client.get(reverse("process_create")).content.decode()
        self.assertIn("nx-step-editor", html)
        self.assertNotIn("{#", html)

    def test_the_page_editor_does_not_print_its_own_comment(self):
        user, client = factories.admin()
        html = client.get(reverse("page_content_list")).content.decode()
        self.assertNotIn("{#", html)
