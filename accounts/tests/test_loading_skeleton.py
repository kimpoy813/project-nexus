"""
The system-wide loading skeleton.

Every page in the system is server-rendered, so a navigation used to be a blank
screen until the next response arrived. The skeleton is painted from
``templates/base.html`` (markup + ``static/css/nexus-skeleton.css``) and taken
away again by ``static/js/nexus-loader.js``.

These tests pin three things that are easy to break:

* every page ships the overlay, the stylesheet and the controller — including
  the pages that do not extend ``base.html`` directly, which reach it through
  ``dashboard_base.html`` / ``_wizard_shell.html``;
* the overlay is visible by default (that is what paints during a load) but is
  hidden again when JavaScript is unavailable, so it can never stick;
* the controller keeps its opt-out hooks and reduced-motion handling.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Profile
from proposals.models import Proposal

from . import factories

ANONYMOUS_PAGES = (
    "/",
    "login",
    "register",
)

OVERLAY_MARKER = 'id="nx-page-skeleton"'
STYLESHEET = "css/nexus-skeleton.css"
CONTROLLER = "js/nexus-loader.js"

#: Decorations that must survive in the stylesheet/script: the overlay is
#: useless if it covers the page forever or ignores a reduced-motion request.
STYLESHEET_MARKERS = (
    ".nx-skel-overlay",
    ".nx-skel--text",
    ".nx-skel-row",
    "prefers-reduced-motion",
    "@media print",
)
CONTROLLER_MARKERS = (
    "NexusSkeleton",
    "data-nx-no-skeleton",
    "pageshow",
    "prefers-reduced-motion",
    "defaultPrevented",
)


class PageSkeletonMarkupTests(TestCase):
    """Pages reachable without an account still ship the skeleton."""

    def _assert_has_skeleton(self, html, *, where):
        self.assertIn(OVERLAY_MARKER, html, f"{where} does not ship the page skeleton")
        self.assertIn(STYLESHEET, html, f"{where} does not load the skeleton stylesheet")
        self.assertIn(CONTROLLER, html, f"{where} does not load the skeleton controller")
        # Visible by default: no `hidden` attribute on the overlay itself. The
        # controller adds it once the page is up.
        self.assertIn('<div id="nx-page-skeleton" class="nx-skel-overlay"', html)

    def test_anonymous_pages_ship_the_skeleton(self):
        for name in ANONYMOUS_PAGES:
            url = name if name.startswith("/") else reverse(name)
            with self.subTest(page=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self._assert_has_skeleton(response.content.decode(), where=url)

    def test_authenticated_pages_ship_the_skeleton(self):
        """Dashboards and the wizard reach base.html through their own shells."""
        roles = [value for value, _ in Profile.ROLE_CHOICES]
        for index, role in enumerate(roles):
            user = factories.make_user(f"skeleton_{index}", role)
            proposal = Proposal.objects.create(created_by=user)
            client = factories.make_client(user)
            for url in (reverse("dashboard_redirect"), reverse("proposal_wizard", args=[proposal.id, 1])):
                with self.subTest(role=role, page=url):
                    response = client.get(url, follow=True)
                    self.assertEqual(response.status_code, 200)
                    self._assert_has_skeleton(response.content.decode(), where=f"{role} {url}")

    def test_admin_pages_ship_the_skeleton(self):
        _, admin_client = factories.admin()
        for url in (reverse("wizard_steps_manager"), reverse("wizard_step_edit", args=[1])):
            with self.subTest(page=url):
                response = admin_client.get(url)
                self.assertEqual(response.status_code, 200)
                self._assert_has_skeleton(response.content.decode(), where=url)

    def test_the_skeleton_is_hidden_when_javascript_is_off(self):
        """A stuck overlay would hide the whole page from a JS-less browser."""
        html = self.client.get(reverse("login")).content.decode()
        noscript = html[html.index("<noscript>"):html.index("</noscript>")]
        self.assertIn("#nx-page-skeleton", noscript)
        self.assertIn("display: none", noscript)


class PageSkeletonAssetTests(SimpleTestCase):
    """The stylesheet and controller keep the pieces the system relies on."""

    def _read(self, relative_path):
        path = Path(settings.BASE_DIR) / "static" / relative_path
        self.assertTrue(path.exists(), f"{relative_path} is missing")
        return path.read_text(encoding="utf-8")

    def test_stylesheet_keeps_the_shapes_and_guards(self):
        css = self._read("css/nexus-skeleton.css")
        for marker in STYLESHEET_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, css)
        # The overlay must paint over the page, not inside it.
        self.assertIn("position: fixed", css)
        self.assertIn("z-index", css)

    def test_controller_keeps_its_api_and_hooks(self):
        js = self._read("js/nexus-loader.js")
        for marker in CONTROLLER_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, js)
        # The public API templates call into.
        for method in ("show:", "hide:", "fill:", "region:", "busy:"):
            with self.subTest(method=method):
                self.assertIn(method, js)


class ContentSkeletonWiringTests(TestCase):
    """Regions that fill in after the page is up paint a skeleton too."""

    def test_proponent_search_paints_rows_while_it_searches(self):
        owner = factories.make_user("skeleton_search_owner", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=owner)
        html = factories.make_client(owner).get(
            reverse("proposal_wizard", args=[proposal.id, 3])
        ).content.decode()

        self.assertIn('id="searchResults"', html)
        # The search paints rows while the request is in flight...
        self.assertIn("NexusSkeleton.fill", html)
        # ...and still replaces them with the real results afterwards.
        self.assertIn("No results.", html)
