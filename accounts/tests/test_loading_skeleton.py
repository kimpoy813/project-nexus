"""
The system-wide loading skeleton.

Every page in the system is server-rendered, so a navigation used to be a blank
screen until the next response arrived. The skeleton is painted from
``templates/base.html`` (markup + ``static/css/nexus-skeleton.css``) and taken
away again by ``static/js/nexus-loader.js``.

The screens are not one layout repeated, so the skeleton is not either: the
overlay carries a layout per page family — landing, auth, dashboard, wizard,
tracker, list, form, record — and each page selects the one that matches its
own structure. ``accounts.context_processors.skeleton_variant`` resolves that
from the route, so no template has to opt in.

These tests pin the things that are easy to break:

* every page ships the overlay, the stylesheet and the controller — including
  the pages that do not extend ``base.html`` directly, which reach it through
  ``_wizard_shell.html``;
* each page family selects **its own** layout, and the layouts really are
  distinct shapes rather than one generic screen under eight names;
* the overlay is visible by default (that is what paints during a load) but is
  hidden again when JavaScript is unavailable, so it can never stick;
* the controller keeps its opt-out hooks and reduced-motion handling.
"""

import json
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import NoReverseMatch, ResolverMatch, get_resolver, resolve, reverse
from django.urls.resolvers import URLPattern, URLResolver

from accounts import context_processors
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
BASE_TEMPLATE = "templates/base.html"

#: Every layout the overlay knows how to paint.
VARIANTS = context_processors.SKELETON_VARIANTS

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


class SkeletonVariantAssertions:
    """Read the layout a rendered page asked the skeleton to paint."""

    VARIANT_MARKER = 'data-nx-variant="'

    def assertSkeletonVariant(self, response, expected, *, where):
        self.assertEqual(response.status_code, 200, f"{where} did not render")
        html = response.content.decode()
        self.assertIn(self.VARIANT_MARKER, html, f"{where} does not select a skeleton layout")
        start = html.index(self.VARIANT_MARKER) + len(self.VARIANT_MARKER)
        found = html[start:html.index('"', start)]
        self.assertEqual(found, expected, f"{where} paints the {found} skeleton, not {expected}")
        return html


class PageSkeletonVariantTests(SkeletonVariantAssertions, TestCase):
    """Each page family paints the skeleton of its own structure.

    These render the real pages through their views: a route that lands in the
    wrong bucket — or a new screen that quietly falls back to the generic
    shape — fails here instead of looking wrong in a browser.
    """

    def test_public_pages_use_the_marketing_layout(self):
        """Landing/CMS pages: full-bleed hero over stacked content sections."""
        urls = ("/", reverse("services_home"), reverse("reports_page"), reverse("achievements_page"))
        for url in urls:
            with self.subTest(page=url):
                self.assertSkeletonVariant(self.client.get(url), "marketing", where=url)

    def test_auth_pages_use_the_split_auth_layout(self):
        """Sign-in screens: brand panel beside the form card."""
        for name in ("login", "register", "password_reset"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertSkeletonVariant(response, "auth", where=name)

    def test_every_role_dashboard_uses_the_dashboard_layout(self):
        """Title bar + 240px nav rail + KPI/queue body, for all seven roles."""
        roles = [value for value, _ in Profile.ROLE_CHOICES]
        for index, role in enumerate(roles):
            user = factories.make_user(f"skeleton_variant_{index}", role)
            client = factories.make_client(user)
            with self.subTest(role=role):
                response = client.get(reverse("dashboard_redirect"), follow=True)
                self.assertSkeletonVariant(response, "dashboard", where=f"{role} dashboard")

    def test_the_proposal_wizard_uses_the_three_rail_layout(self):
        """Stepper rail | form column | context rail."""
        author = factories.make_user("skeleton_wizard", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=author)
        url = reverse("proposal_wizard", args=[proposal.id, 1])
        self.assertSkeletonVariant(
            factories.make_client(author).get(url), "wizard", where="proposal wizard"
        )

    def test_admin_lists_and_forms_paint_different_layouts(self):
        """A CRUD list is a table; a CRUD form is a field grid. Not the same."""
        _, admin_client = factories.admin()
        list_url = reverse("wizard_steps_manager")
        form_url = reverse("wizard_step_edit", args=[1])
        self.assertSkeletonVariant(admin_client.get(list_url), "list", where=list_url)
        self.assertSkeletonVariant(admin_client.get(form_url), "form", where=form_url)
        self.assertSkeletonVariant(
            admin_client.get(reverse("admin_create_account")),
            "form",
            where="admin create account",
        )

    def test_accomplishment_report_screens_split_into_list_and_form(self):
        coordinator = factories.make_user(
            "skeleton_accomp", Profile.ROLE_DEPARTMENT_COORDINATOR, department="Computer Science"
        )
        client = factories.make_client(coordinator)
        self.assertSkeletonVariant(
            client.get(reverse("accomplishment_reports_list")), "list", where="reports list"
        )
        self.assertSkeletonVariant(
            client.get(reverse("accomplishment_report_create")), "form", where="report form"
        )

    def test_profile_screens_split_into_record_and_form(self):
        user = factories.make_user("skeleton_profile", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        self.assertSkeletonVariant(
            client.get(reverse("profile_view")), "record", where="profile"
        )
        self.assertSkeletonVariant(
            client.get(reverse("profile_edit")), "form", where="profile edit"
        )

    def test_proposal_trackers_use_the_progress_layout(self):
        """Progress header + two-thirds main card + side cards."""
        author = factories.make_user("skeleton_tracker", Profile.ROLE_FACULTY)
        proposal = Proposal.objects.create(created_by=author)
        client = factories.make_client(author)
        pages = {
            "proposal_moa_tracker": reverse("proposal_moa_tracker", args=[proposal.id]),
            "proposal_implementation_tracker": reverse(
                "proposal_implementation_tracker", args=[proposal.id]
            ),
            "proposal_storage": reverse("proposal_storage", args=[proposal.id]),
            "proposal_upload_signed_proposal": reverse(
                "proposal_upload_signed_proposal", args=[proposal.id]
            ),
        }
        reachable = 0
        for name, url in pages.items():
            with self.subTest(page=name):
                response = client.get(url)
                if response.status_code != 200:
                    # Some trackers need a later lifecycle state; the workflow
                    # suite covers those.
                    continue
                reachable += 1
                self.assertSkeletonVariant(response, "tracker", where=name)
        self.assertGreater(reachable, 0, "no tracker page rendered for this proposal")


class SkeletonVariantResolverTests(SimpleTestCase):
    """The route → layout resolver, including the rules for routes not listed."""

    def _variant_for(self, url_name="", path="/"):
        request = RequestFactory().get(path)
        request.resolver_match = (
            ResolverMatch(lambda: None, (), {}, url_name) if url_name else None
        )
        return context_processors._resolve_skeleton_variant(request)

    def test_listed_routes_resolve_explicitly(self):
        cases = {
            "details_page": "marketing",
            "services_home": "marketing",
            "login": "auth",
            "logout": "auth",
            "logout_idle": "auth",
            "password_reset_confirm": "auth",
            "director_dashboard": "dashboard",
            "admin_edit_user": "form",
            "admin_create_account": "form",
            "admin_site_control": "dashboard",
            "proposal_wizard": "wizard",
            "proposal_moa_tracker": "tracker",
            "manage_roles": "record",
            "profile_view": "record",
        }
        for url_name, expected in cases.items():
            with self.subTest(route=url_name):
                self.assertEqual(self._variant_for(url_name), expected)

    def test_crud_routes_resolve_by_name_ending(self):
        """A route added later follows the shape of its kind, not the default."""
        cases = {
            "widgets_list": "list",
            "widget_manager": "list",
            "widget_create": "form",
            "widget_edit": "form",
            "widget_dashboard": "dashboard",
        }
        for url_name, expected in cases.items():
            with self.subTest(route=url_name):
                self.assertEqual(self._variant_for(url_name), expected)

    def test_an_explicit_route_beats_its_name_ending(self):
        # `admin_content_dashboard` ends in `_dashboard` but is a card stack,
        # not a dashboard with a nav rail.
        self.assertEqual(self._variant_for("admin_content_dashboard"), "record")

    def test_unmatched_routes_fall_back_by_area_then_default(self):
        self.assertEqual(self._variant_for("brand_new_thing", "/somewhere/else/"), "record")
        self.assertEqual(self._variant_for("", "/dashboard/something-new/"), "dashboard")
        self.assertEqual(self._variant_for("", "/admin/something-new/"), "list")
        # CRUD path endings beat the /admin/ list prefix when the url name is unknown.
        self.assertEqual(self._variant_for("", "/admin/widgets/1/edit/"), "form")
        self.assertEqual(self._variant_for("", "/admin/widgets/new/"), "form")

    def test_a_request_without_a_resolved_route_never_raises(self):
        """Runs on error pages too, where nothing matched."""
        self.assertEqual(self._variant_for(), context_processors.SKELETON_DEFAULT)
        request = RequestFactory().get("/")
        request.resolver_match = None
        del request.path
        self.assertEqual(
            context_processors._resolve_skeleton_variant(request),
            context_processors.SKELETON_DEFAULT,
        )


class SkeletonLayoutMarkupTests(SimpleTestCase):
    """The overlay ships every layout, and only the selected one paints."""

    def _read(self, relative_path):
        path = Path(settings.BASE_DIR) / relative_path
        self.assertTrue(path.exists(), f"{relative_path} is missing")
        return path.read_text(encoding="utf-8")

    def test_every_layout_is_in_the_overlay_and_gated_by_the_stylesheet(self):
        markup = self._read(BASE_TEMPLATE)
        css = self._read(f"static/{STYLESHEET}")
        for name in VARIANTS:
            with self.subTest(layout=name):
                self.assertIn(f"nx-skel-l--{name}", markup, f"{name} layout is not rendered")
                self.assertIn(f'[data-nx-variant="{name}"]', css, f"{name} layout is never shown")

    def test_layouts_are_hidden_unless_selected(self):
        """Otherwise all eight would paint on top of each other."""
        css = self._read(f"static/{STYLESHEET}")
        self.assertIn(".nx-skel-l { display: none; }", css)

    def test_the_navbar_shape_is_shared_rather_than_repeated(self):
        markup = self._read(BASE_TEMPLATE)
        self.assertEqual(markup.count("nx-skel-overlay__bar"), 1)

    def test_navigation_declares_the_shape_it_leads_to(self):
        """A link can carry the destination's layout so the controller can
        switch to it before painting."""
        markup = self._read(BASE_TEMPLATE)
        for hint in ("marketing", "dashboard", "auth", "list", "form", "record"):
            with self.subTest(hint=hint):
                self.assertIn(f'data-nx-skeleton="{hint}"', markup)

    def test_the_controller_can_switch_layouts(self):
        js = self._read(f"static/{CONTROLLER}")
        self.assertIn("variant:", js, "the controller no longer exposes variant()")
        self.assertIn("data-nx-skeleton", js)
        self.assertIn("data-nx-variant", js)
        # `?nx-skeleton` holds the overlay up so a layout can be reviewed.
        self.assertIn("nx-skeleton", js)
        # Navigation paints the page being gone *to*, not the one being left.
        self.assertIn("variantForPath", js)
        self.assertIn("POST /login/", js)
        self.assertIn('p === "/logout"', js)
        # In-wizard step changes are not a page load, so they must not cover the site.
        self.assertIn("[data-nx-wizard]", js)


class SkeletonDestinationTests(TestCase):
    """Navigation must paint the *next* page, not the current one.

    The login form posts back to itself, so without a destination hint the
    overlay would keep the auth layout while the dashboard is loading. Logout
    is a GET of the current session that then redirects to login, so without
    a hint it would keep whatever page the user was on. The same pattern
    applies to every other POST-then-redirect form in the system.
    """

    def test_login_form_declares_the_dashboard_it_redirects_to(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertRegex(html, r"<form[^>]*data-nx-skeleton=\"dashboard\"")

    def test_register_form_stays_on_the_auth_family(self):
        html = self.client.get(reverse("register")).content.decode()
        self.assertRegex(html, r"<form[^>]*data-nx-skeleton=\"auth\"")

    def test_logout_links_declare_the_auth_screen_they_redirect_to(self):
        user = factories.make_user("skel_logout", Profile.ROLE_FACULTY)
        html = factories.make_client(user).get("/").content.decode()
        tags = re.findall(r"<a\b[^>]*href=\"[^\"]*logout[^\"]*\"[^>]*>", html, flags=re.I)
        self.assertGreaterEqual(len(tags), 2, "desktop and mobile logout links")
        for tag in tags:
            self.assertIn('data-nx-skeleton="auth"', tag, tag)

    def test_idle_logout_paints_the_auth_skeleton_before_redirecting(self):
        user = factories.make_user("skel_idle", Profile.ROLE_FACULTY)
        html = factories.make_client(user).get("/").content.decode()
        self.assertIn('NexusSkeleton.show("auth")', html)

    def test_brand_home_link_declares_the_marketing_landing(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r"<a[^>]*aria-label=\"NExUS Home\"[^>]*data-nx-skeleton=\"marketing\"")

    def test_profile_edit_form_declares_the_record_it_redirects_to(self):
        user = factories.make_user("skel_profile_dest", Profile.ROLE_FACULTY)
        html = factories.make_client(user).get(reverse("profile_edit")).content.decode()
        self.assertRegex(html, r"<form[^>]*data-nx-skeleton=\"record\"")

    def test_admin_create_account_form_declares_the_dashboard_it_redirects_to(self):
        _, admin_client = factories.admin()
        html = admin_client.get(reverse("admin_create_account")).content.decode()
        self.assertRegex(html, r"<form[^>]*data-nx-skeleton=\"dashboard\"")

    def test_admin_dashboard_post_bounces_paint_the_dashboard(self):
        _, admin_client = factories.admin()
        html = admin_client.get(reverse("admin_dashboard")).content.decode()
        self.assertRegex(html, r"<form[^>]*action=\"[^\"]*manage-roles[^\"]*\"[^>]*data-nx-skeleton=\"dashboard\"")
        self.assertRegex(html, r"<form[^>]*action=\"[^\"]*site-control[^\"]*\"[^>]*data-nx-skeleton=\"dashboard\"")

    def test_services_start_proposal_declares_the_wizard(self):
        html = self.client.get(reverse("services_home")).content.decode()
        self.assertRegex(html, r"<a[^>]*href=\"[^\"]*proposals/new[^\"]*\"[^>]*data-nx-skeleton=\"wizard\"")


_JS_DEST_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const start = src.indexOf("function normalizePath");
const end = src.indexOf("function variantForUrl");
if (start < 0 || end < 0) {
  console.error("could not extract functions", start, end);
  process.exit(1);
}
eval(src.slice(start, end));
const paths = JSON.parse(fs.readFileSync(0, "utf8"));
const out = {};
for (const p of paths) out[p] = variantForPath(p);
process.stdout.write(JSON.stringify(out));
"""


def _walk_named_patterns(resolver, found):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            _walk_named_patterns(pattern, found)
        elif isinstance(pattern, URLPattern) and pattern.name:
            found.append(pattern)


_SAMPLE_KWARGS = {
    "proposal_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "step": 1,
    "pk": 1,
    "user_id": 1,
    "step_no": 1,
    "evaluator_id": 1,
    "uidb64": "MQ",
    "token": "abc-def",
    "slug": "home",
    "round_no": 1,
    "file_type": "docx",
    "attachment_id": 1,
    "document_type": "endorsement",
}


def _sample_kwargs(pattern):
    converters = getattr(pattern.pattern, "converters", None) or {}
    return {name: _SAMPLE_KWARGS[name] for name in converters if name in _SAMPLE_KWARGS}


class SkeletonClientDestinationParityTests(SimpleTestCase):
    """Every named app URL: JS dest inference matches the Python page layout.

    The overlay on the way *out* is keyed by path (the click only has a URL).
    The overlay on the way *in* is keyed by Django url name. If those two
    disagree, login/logout-style bugs reappear on whichever screen drifted.
    """

    def test_js_path_rules_match_python_for_every_named_url(self):
        if not shutil.which("node"):
            self.skipTest("node is required to evaluate variantForPath")

        patterns = []
        _walk_named_patterns(get_resolver(), patterns)

        paths = {}
        for pattern in patterns:
            try:
                path = reverse(pattern.name, kwargs=_sample_kwargs(pattern))
            except NoReverseMatch:
                continue
            paths.setdefault(path, pattern.name)

        self.assertGreater(len(paths), 80, "too few named URLs reversed; walker is broken")

        loader = Path(settings.BASE_DIR) / "static" / "js" / "nexus-loader.js"
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as harness:
            harness.write(_JS_DEST_HARNESS)
            harness_path = harness.name
        try:
            proc = subprocess.run(
                ["node", harness_path, str(loader)],
                input=json.dumps(list(paths)).encode(),
                capture_output=True,
                check=False,
            )
        finally:
            Path(harness_path).unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        js_map = json.loads(proc.stdout)

        factory = RequestFactory()
        mismatches = []
        for path, name in paths.items():
            request = factory.get(path)
            try:
                request.resolver_match = resolve(path)
            except Exception:
                request.resolver_match = None
            python = context_processors._resolve_skeleton_variant(request)
            javascript = js_map.get(path)
            if python != javascript:
                mismatches.append(f"{name} {path} py={python} js={javascript}")
        self.assertEqual(mismatches, [], "JS dest != Python layout:\n" + "\n".join(mismatches))

    def test_controller_covers_the_paths_that_used_to_drift(self):
        js = (Path(settings.BASE_DIR) / "static" / "js" / "nexus-loader.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            'p === "/logout"',
            "/(create|edit|new)$",
            "/admin/pages/",
            "/admin/create-account",
            "/admin/site-control",
            'normalizePath(path) === "/login" && method === "POST"',
            'normalizePath(path) === "/manage-roles" && method === "POST"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)
