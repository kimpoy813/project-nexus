"""The UX contract the screens are held to.

Nielsen's ten heuristics are a checklist, not a style choice, so the parts a
test can hold down are pinned here: the password fields say how to reveal and
how to satisfy them, a failed submit puts the user at the summary, a slow save
says it is working, and nothing on the page guesses a password. The judgement
calls behind the rest live in ``docs/NIELSEN_HEURISTICS_AUDIT.md``.

These tests deliberately assert *behaviour a user can see* — attributes,
labels, focus targets — rather than markup details, so the templates can be
restyled without rewriting them.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.forms import NexusSetPasswordForm
from accounts.models import Profile, SiteConfiguration

from . import factories


def password_inputs(html):
    """Every ``<input type="password">`` tag in a rendered page."""
    return re.findall(r"<input[^>]*type=\"password\"[^>]*>", html)


class PasswordFieldTests(TestCase):
    """Password fields are visible, understandable and recoverable."""

    def test_the_reveal_toggle_is_loaded_on_every_page(self):
        """One shared control, so the eye never appears on some screens only."""
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn("js/nexus-password.js", html)
        self.assertIn("js/nexus-forms.js", html)

    def test_the_login_password_can_be_revealed(self):
        html = self.client.get(reverse("login")).content.decode()
        field = password_inputs(html)
        self.assertEqual(len(field), 1, "the login form has exactly one password field")
        self.assertIn('id="login-password"', field[0])
        self.assertIn('autocomplete="current-password"', field[0])
        # The toggle is added by the shared script, which is included above.
        self.assertIn("nexus-password.js", html)

    def test_a_new_password_explains_its_rules_before_it_is_typed(self):
        form = NexusSetPasswordForm(user=factories.make_user("rules_user"))
        rendered = str(form["new_password1"])

        self.assertIn('autocomplete="new-password"', rendered)
        self.assertIn('data-nx-password-rules="length,number,uppercase"', rendered)
        self.assertIn('spellcheck="false"', rendered)
        self.assertIn('autocapitalize="none"', rendered)

    def test_the_confirmation_points_at_the_field_it_must_match(self):
        form = NexusSetPasswordForm(user=factories.make_user("match_user"))
        self.assertIn('data-nx-match="id_new_password1"', str(form["new_password2"]))

    def test_no_template_keeps_its_own_password_rules_script(self):
        """The rules are defined once (js/nexus-password.js), not per page."""
        for template in ("register.html", "password_reset_confirm.html"):
            with self.subTest(template=template):
                text = (
                    Path(settings.BASE_DIR) / "accounts" / "templates" / "accounts" / template
                ).read_text(encoding="utf-8")
                self.assertNotIn('id="password-rules"', text)
                self.assertNotIn("getElementById(\"length\")", text)

    def test_every_password_field_on_the_auth_pages_has_a_label(self):
        pages = [reverse("login"), reverse("register"), reverse("password_reset")]
        for url in pages:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                for tag in password_inputs(html):
                    field_id = re.search(r'id="([^"]+)"', tag)
                    self.assertIsNotNone(field_id, f"a password field without an id on {url}")
                    self.assertIn(
                        f'for="{field_id.group(1)}"',
                        html,
                        f"no <label for> for {field_id.group(1)} on {url}",
                    )

    def test_the_reset_form_renders_the_reveal_attributes(self):
        user = factories.make_user("reset_user")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        url = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})

        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-nx-password-rules="length,number,uppercase"', html)
        self.assertIn('data-nx-match="new_password1"', html)
        # The rules are also readable with JavaScript switched off.
        self.assertIn("At least 8 characters", html)


class ErrorRecoveryTests(TestCase):
    """Heuristic 9: help users recognise, diagnose and recover from errors."""

    def test_a_failed_sign_in_puts_the_error_where_focus_lands(self):
        response = self.client.post(
            reverse("login"),
            {"username": "nobody-here", "password": "wrong-password"},
        )
        html = response.content.decode()
        self.assertIn("data-nx-error-summary", html)
        self.assertIn('role="alert"', html)
        self.assertIn('tabindex="-1"', html)

    def test_a_rejected_registration_lists_the_problems_with_links(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "Test Person",
                "username": "ux-register-user",
                "email": "ux-register@example.com",
                "campus": "Main Campus",
                "college": "",
                "department": "",
                "password": "short",
                "confirm_password": "short",
            },
        )
        html = response.content.decode()
        self.assertIn("data-nx-error-summary", html)
        self.assertIn("Please correct the following before continuing:", html)
        # Each problem links to the field it belongs to, so the fix is one
        # keystroke away instead of a hunt through the form.
        self.assertRegex(html, r'<a href="#id_password"')

    def test_a_registration_page_without_errors_has_no_summary(self):
        html = self.client.get(reverse("register")).content.decode()
        self.assertNotIn("data-nx-error-summary", html)


class SystemStatusTests(TestCase):
    """Heuristic 1: the interface says what is happening, including waiting."""

    def test_slow_submits_say_they_are_working(self):
        for url in (reverse("login"), reverse("register")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("data-nx-busy", html)

    def test_the_admin_forms_report_that_they_are_saving(self):
        _, client = factories.admin("ux_admin")
        response = client.get(reverse("admin_create_account"))
        self.assertContains(response, "data-nx-busy")
        self.assertContains(response, "Creating account…")
        # Creating an account is a decision: there is a way back out.
        self.assertContains(response, reverse("admin_dashboard"))


class HeuristicsDocumentationTests(TestCase):
    """The audit is part of the product, so it cannot silently go stale."""

    def test_the_ten_heuristics_are_documented(self):
        path = Path(settings.BASE_DIR) / "docs" / "NIELSEN_HEURISTICS_AUDIT.md"
        self.assertTrue(path.is_file(), "docs/NIELSEN_HEURISTICS_AUDIT.md is missing")

        text = path.read_text(encoding="utf-8")
        for number in range(1, 11):
            with self.subTest(heuristic=number):
                self.assertIn(f"## {number}.", text)
        # The document points at the tests that hold it down, so a rewrite that
        # drops the evidence is visible in review.
        self.assertIn("test_ux_heuristics.py", text)


class HelpPageTests(TestCase):
    """Heuristic 10: the documentation is a page, not a promise."""

    def test_anyone_can_read_the_help_page(self):
        response = self.client.get(reverse("help_page"))
        self.assertEqual(response.status_code, 200)

    def test_the_help_page_answers_what_the_statuses_mean(self):
        html = self.client.get(reverse("help_page")).content.decode()
        # One row per status a proposal can be in; the page is only useful if it
        # agrees with the model.
        from proposals.models import Proposal

        for value, label in Proposal.ProposalStatus.choices:
            with self.subTest(status=value):
                self.assertIn(label.split(" / ")[0].split(" & ")[0], html)

    def test_the_help_page_is_reachable_from_the_chrome(self):
        html = self.client.get(reverse("details_page")).content.decode()
        self.assertIn(reverse("help_page"), html)

    def test_the_help_page_does_not_invent_contact_details(self):
        config = SiteConfiguration.get_solo()
        config.contact_email = ""
        config.facebook_url = ""
        config.save()

        html = self.client.get(reverse("help_page")).content.decode()
        # With nothing published, the page says so instead of guessing.
        self.assertIn("have not been published", html)
        self.assertNotIn("mailto:@", html)


class AccessibilityBasicsTests(TestCase):
    """Cross-cutting checks that support several heuristics at once."""

    def test_the_skip_link_leads_to_the_main_region(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn('href="#main-content"', html)
        self.assertIn('id="main-content"', html)

    def test_the_login_navigation_keeps_its_accessible_name(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn('aria-label="NExUS Home"', html)

    def test_a_password_is_posted_and_never_echoed_back(self):
        """Credentials travel in the POST body and are not re-rendered."""
        html = self.client.get(reverse("login")).content.decode()
        self.assertRegex(html, r'<form[^>]*method="POST"')
        for tag in password_inputs(html):
            self.assertNotIn("value=", tag, "a password field must never be pre-filled")

    def test_the_debug_sign_in_page_is_not_public(self):
        """Heuristic 5: a developer's CSRF dump has no place on the live site."""
        self.assertEqual(self.client.get(reverse("debug_login")).status_code, 404)
