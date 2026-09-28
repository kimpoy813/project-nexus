"""Semantic smoke tests for the shared UI, not pixel snapshots."""

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from proposals.models import Proposal

from . import factories


class DesignSystemSmokeTests(TestCase):
    def test_public_pages_keep_the_shared_design_and_editable_content(self):
        for url in ("/", reverse("services_home"), reverse("reports_page")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "css/nexus-ui.css")
                self.assertContains(response, "css/nexus-tailwind.css")
                self.assertContains(response, "vendor/alpine.min.js")
                self.assertNotContains(response, "cdn.tailwindcss.com")
                self.assertContains(response, "css/public-pages.css")
                self.assertContains(response, "fonts/public-sans-latin-variable.woff2")
                self.assertContains(response, "nx-public-hero")

    def test_auth_forms_have_a_brand_panel_and_labelled_form_heading(self):
        for name in ("login", "register", "password_reset"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="nx-auth__panel"')
                self.assertContains(response, 'class="nx-auth__header"')
                self.assertContains(response, 'class="nx-auth__body"')

    def test_faculty_empty_state_offers_next_steps(self):
        user = factories.make_user("design_faculty", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        response = client.get(reverse("faculty_dashboard"))
        self.assertContains(response, "No proposals yet")
        self.assertContains(response, 'class="nx-empty nx-getting-started"')
        self.assertContains(response, reverse("proposal_create"))
        self.assertContains(response, "See how it works")

    def test_expired_password_link_explains_next_step(self):
        response = self.client.get(reverse("password_reset_confirm", kwargs={
            "uidb64": "bad-uid", "token": "bad-token",
        }))
        self.assertContains(response, "This reset link has expired")
        self.assertContains(response, "Request another link")
        self.assertNotContains(response, 'name="new_password1"')

    def test_wizard_options_show_labels_and_work_as_buttons(self):
        user = factories.make_user("design_wizard", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=user)
        response = factories.make_client(user).get(reverse("proposal_wizard", args=[proposal.id, 1]))
        self.assertContains(response, "Research-based (Faculty)")
        self.assertContains(response, 'role="group" aria-labelledby="extension-type-label"')
        self.assertContains(response, 'class="ext-chip')
        self.assertNotContains(response, "('RESEARCH_FACULTY',")

    def test_profile_uses_a_definition_list_not_unlabelled_values(self):
        user = factories.make_user("design_profile", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        response = client.get(reverse("profile_view"))
        self.assertContains(response, '<dl class="nx-profile__grid">')
        self.assertContains(response, "<dt>Username</dt><dd>design_profile</dd>")

    def test_error_pages_keep_a_way_back(self):
        response = self.client.get("/not-a-nexus-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, "Go to home", status_code=404)
        # The 500 page must render without a request or a working database.
        rendered = render_to_string("500.html")
        self.assertIn("Return to home", rendered)
        self.assertIn("css/nexus-ui.css", rendered)
