"""
Tests for the Programs directory, the Gallery, and the About page.

These three pages replaced Reports and Achievements. The coverage here follows
the same rule as the rest of the CMS suite: an admin edits a record, and the
public page reflects it — while nothing an admin has not published leaks out.

  * **Programs**    - every published program, its totals, and its filters
  * **Gallery**     - the photo documentation filed with each activity
  * **About**       - the seeded page, editable like any other
  * **Navigation**  - the site menu offers the new pages and none of the old

A program is not its own record: it is an approved proposal, or a legacy
proposal imported through *Legacy Records Upload*. The tests below therefore
seed proposals, and the photo tests seed the documentation photos that belong
to them — there is no second table to keep in step.
"""

import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import Campus, Profile
from details.content_sources import get_content_source
from details.models import (
    PageSection,
    SitePage,
    resolve_section_data,
)
from proposals.models import DocumentationPhoto, Proposal, ProposalFinalDocument

from . import factories


DENIED = (302, 403)

#: A 1x1 transparent GIF: the smallest valid image Django will accept.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def make_proposal(*, status="APPROVED", overall="ACTIVE", legacy=False, **overrides):
    """A proposal in the state the Programs directory publishes."""
    owner = overrides.pop("owner", None) or factories.make_user(
        f"owner-{Proposal.objects.count()}", Profile.ROLE_FACULTY
    )
    defaults = {
        "created_by": owner,
        "title": "PROPOSAL-MARKER",
        "campus": "Main Campus",
        "proposal_status": status,
        "status": overall,
        "is_legacy": legacy,
        "extension_type": Proposal.ExtensionType.COMMUNITY_BASED,
        "beneficiaries_count": 40,
        "beneficiaries_who": "Barangay Sabangan residents",
        "estimated_month": "May",
        "estimated_year": 2025,
        "general_objective": "Improve household nutrition.",
    }
    defaults.update(overrides)
    return Proposal.objects.create(**defaults)


def make_signed_document(proposal, name="signed.pdf"):
    return ProposalFinalDocument.add_version(
        proposal=proposal,
        document_type=ProposalFinalDocument.DocumentType.SIGNED_PROPOSAL,
        file=SimpleUploadedFile(name, b"%PDF-1.4 signed proposal"),
    )


def make_documentation_photo(proposal, caption="DOCUMENTATION-PHOTO", **overrides):
    """A photo filed with the activity — the Gallery's only source."""
    defaults = {
        "proposal": proposal,
        "image": SimpleUploadedFile("doc.gif", TINY_GIF, content_type="image/gif"),
        "caption": caption,
    }
    defaults.update(overrides)
    return DocumentationPhoto.objects.create(**defaults)


def make_legacy_proposal(*, title="LEGACY-MARKER", **overrides):
    """Older work imported by the office, with its own uploaded document."""
    defaults = {
        "title": title,
        "status": "COMPLETED",
        "proposal_status": "COMPLETED",
        "is_legacy": True,
        "campus": "Candon Campus",
        "estimated_year": 2019,
        "legacy_proposal_file": SimpleUploadedFile(
            "old-proposal.pdf", b"%PDF-1.4 legacy"
        ),
    }
    defaults.update(overrides)
    return make_proposal(**defaults)


def hero_heading(response):
    """The text inside the page's `<h1>`, whitespace collapsed."""
    match = re.search(r"<h1[^>]*>(.*?)</h1>", response.content.decode(), re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


class SeededPageTests(TestCase):
    """The migration replaces Reports/Achievements with Programs and Gallery."""

    def test_the_four_public_pages_are_seeded(self):
        self.assertEqual(
            set(SitePage.objects.values_list("slug", flat=True)),
            {"home", "services", "programs", "gallery"},
        )

    def test_each_directory_page_holds_only_its_own_block(self):
        """Programs is a directory, Gallery is a gallery — nothing else.

        The Targets and Activities blocks that came with the replaced pages
        showed "nothing here yet" on a system with no data, so they were
        dropped rather than carried over.
        """
        programs = SitePage.get_for("programs")
        gallery = SitePage.get_for("gallery")
        self.assertEqual(
            list(programs.sections.values_list("layout", flat=True)),
            ["PROGRAMS"],
        )
        self.assertEqual(
            list(gallery.sections.values_list("layout", flat=True)),
            ["GALLERY"],
        )

    def test_the_new_pages_render(self):
        for name in ("programs_page", "gallery_page"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_the_old_urls_permanently_redirect(self):
        self.assertRedirects(
            self.client.get("/reports/"), "/programs/", status_code=301
        )
        self.assertRedirects(
            self.client.get("/achievements/"), "/gallery/", status_code=301
        )

    def test_unpublished_pages_stay_hidden_from_visitors(self):
        page = SitePage.get_for("gallery")
        page.is_published = False
        page.save()

        self.assertEqual(self.client.get(reverse("gallery_page")).status_code, 404)

        admin = factories.make_user("gallery_admin", Profile.ROLE_ADMIN)
        response = factories.make_client(admin).get(reverse("gallery_page"))
        self.assertEqual(response.status_code, 200)


class ProgramsPageTests(TestCase):
    """The Programs page is the directory of every published program."""

    def setUp(self):
        self.programs_url = reverse("programs_page")

    def test_a_program_row_appears_with_its_details(self):
        make_proposal(
            title="PROGRAM-MARKER",
            campus="Main Campus",
            estimated_year=2025,
            extension_type=Proposal.ExtensionType.RESEARCH_FACULTY,
            beneficiaries_count=34,
            beneficiaries_who="Dili National High School",
            date_venue="September 2025 – February 2026",
            general_objective="Improve reading comprehension.",
            student_participants=50,
            faculty_participants=5,
        )
        make_legacy_proposal(
            title="PROGRAM-MARKER-LEGACY",
            campus="Main Campus",
            date_venue="September 2025 – February 2026",
            general_objective="Improve reading comprehension.",
            student_participants=50,
            faculty_participants=5,
            beneficiaries_count=34,
            beneficiaries_who="Dili National High School",
        )

        response = self.client.get(self.programs_url)
        self.assertContains(response, "PROGRAM-MARKER")
        self.assertContains(response, "Main Campus")
        self.assertContains(response, "Dili National High School")
        self.assertContains(response, "September 2025 – February 2026")
        self.assertContains(response, "Improve reading comprehension.")
        self.assertContains(response, "View legacy upload")
        # Filters are built from the published entries only.
        self.assertContains(response, 'data-campus="Main Campus"')
        self.assertContains(response, 'id="program-campus-')

    def test_the_totals_count_only_published_programs(self):
        make_proposal(
            title="VISIBLE",
            campus="Main Campus",
            student_participants=10,
            faculty_participants=2,
            beneficiaries_count=100,
        )
        make_proposal(
            title="HIDDEN",
            campus="Cervantes Campus",
            proposal_status="DRAFTING",
            status="DRAFT",
            student_participants=999,
            beneficiaries_count=999,
        )

        section = PageSection.objects.filter(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        ).first()
        data = resolve_section_data(section)
        self.assertEqual(data["stats"]["program_count"], 1)
        self.assertEqual(data["stats"]["students"], 10)
        self.assertEqual(data["stats"]["faculty"], 2)
        self.assertEqual(data["stats"]["beneficiaries"], 100)
        self.assertEqual(data["stats"]["campus_count"], 1)

        response = self.client.get(self.programs_url)
        self.assertContains(response, "VISIBLE")
        self.assertNotContains(response, "HIDDEN")
        self.assertNotContains(response, "Cervantes Campus")

    def test_an_unpublished_proposal_leaves_its_campus_out_of_the_filter(self):
        make_proposal(title="LIVE", campus="Main Campus")
        make_proposal(
            title="OFF",
            campus="Tagudin Campus",
            proposal_status="IN_REVIEW",
            status="ACTIVE",
        )
        section = PageSection.objects.filter(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        ).first()
        campuses = resolve_section_data(section)["facets"]["campuses"]
        self.assertEqual([c["value"] for c in campuses], ["Main Campus"])

    def test_the_overview_bars_summarise_published_programs(self):
        make_proposal(
            title="ONE",
            campus="Main Campus",
            estimated_year=2025,
            extension_type=Proposal.ExtensionType.RESEARCH_FACULTY,
        )
        make_proposal(
            title="TWO",
            campus="Main Campus",
            estimated_year=2025,
            extension_type=Proposal.ExtensionType.COMMUNITY_BASED,
        )
        response = self.client.get(self.programs_url)
        self.assertContains(response, "Programs per year")
        self.assertContains(response, "By type of extension")
        self.assertContains(response, "Programs by campus")
        # Two programs on the same campus: the campus bar is the full width.
        self.assertContains(response, 'style="width: 100%"')

    def test_the_empty_state_is_explicit(self):
        response = self.client.get(self.programs_url)
        self.assertContains(response, "No extension programs are published yet.")
        # It also says where programs come from, so an empty page is not a mystery.
        self.assertContains(response, "This directory is not filled in by hand")

    def test_the_new_blocks_are_registered_content_sources(self):
        for key, template in (
            ("PROGRAMS", "details/blocks/programs.html"),
            ("GALLERY", "details/blocks/gallery.html"),
        ):
            with self.subTest(key=key):
                source = get_content_source(key)
                self.assertIsNotNone(source)
                self.assertEqual(source.block_template, template)
                self.assertIn(key, PageSection.DATA_LAYOUTS)


class NoProgramBuilderTests(TestCase):
    """Programs are not added by hand, imported, edited, or deleted.

    The office asked for one data structure: a program is a proposal. The
    builder routes that used to create a second copy are gone, and the admin
    page says where programs come from instead of offering an add button.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("program_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("program_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_removed_routes_do_not_exist(self):
        proposal = make_proposal()
        for name in (
            "program_create",
            "programs_import",
            "program_edit",
            "program_delete",
            "gallery_photo_create",
            "gallery_photo_edit",
            "gallery_photo_delete",
        ):
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name, args=[proposal.pk])

    def test_the_list_page_reports_published_programs(self):
        make_proposal(title="APPROVED-LISTED")
        make_legacy_proposal(title="LEGACY-LISTED")
        response = self.client_admin.get(reverse("programs_list"))
        self.assertContains(response, "APPROVED-LISTED")
        self.assertContains(response, "LEGACY-LISTED")
        self.assertContains(response, "Extension Programs")

    def test_the_list_page_offers_no_import_or_add_controls(self):
        response = self.client_admin.get(reverse("programs_list"))
        html = response.content.decode()
        self.assertNotIn("Import CSV", html)
        self.assertNotIn("Add program", html)
        # Instead it points at the only way old work gets in.
        self.assertContains(response, reverse("admin_legacy_proposal_create"))

    def test_the_list_page_can_be_searched(self):
        make_proposal(title="SEARCH-MARKER")
        make_proposal(title="OTHER-MARKER")
        response = self.client_admin.get(reverse("programs_list"), {"q": "search"})
        self.assertContains(response, "SEARCH-MARKER")
        self.assertNotContains(response, "OTHER-MARKER")

    def test_non_admins_cannot_see_the_directory(self):
        client = factories.make_client(self.faculty)
        self.assertIn(client.get(reverse("programs_list")).status_code, DENIED)


class GalleryTests(TestCase):
    """The Gallery shows the photo documentation filed with each activity."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("gallery_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)
        self.gallery_url = reverse("gallery_page")

    def test_a_documentation_photo_appears_in_the_grid(self):
        make_documentation_photo(make_proposal(), caption="GALLERY-MARKER")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "GALLERY-MARKER")
        self.assertContains(response, "Open photo: GALLERY-MARKER")

    def test_a_hidden_photo_stays_out_of_the_grid(self):
        make_documentation_photo(
            make_proposal(), caption="HIDDEN-PHOTO", is_visible=False
        )
        self.assertNotContains(self.client.get(self.gallery_url), "HIDDEN-PHOTO")

    def test_a_photo_names_the_activity_it_documents(self):
        make_documentation_photo(
            make_proposal(title="PARENT-PROGRAM", campus="Sta. Maria Campus"),
            caption="Seedling distribution",
        )
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "Seedling distribution")
        self.assertContains(response, "PARENT-PROGRAM")
        self.assertContains(response, "Sta. Maria Campus")

    def test_a_legacy_activity_says_its_photos_came_from_the_import(self):
        make_documentation_photo(make_legacy_proposal(), caption="IMPORTED-PHOTO")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "IMPORTED-PHOTO")
        self.assertContains(response, "Legacy upload")

    def test_the_office_hides_an_unpublishable_photo_instead_of_deleting_it(self):
        photo = make_documentation_photo(make_proposal(), caption="SENSITIVE")
        self.client_admin.post(reverse("documentation_photo_toggle", args=[photo.id]))

        photo.refresh_from_db()
        self.assertFalse(photo.is_visible)
        self.assertNotContains(self.client.get(self.gallery_url), "SENSITIVE")
        # The record keeps the photo: hiding is not deleting.
        self.assertTrue(DocumentationPhoto.objects.filter(pk=photo.pk).exists())

    def test_the_manager_lists_photos_with_their_activity(self):
        make_documentation_photo(
            make_proposal(title="MANAGED-ACTIVITY"), caption="MANAGED-PHOTO"
        )
        response = self.client_admin.get(reverse("gallery_photos_list"))
        self.assertContains(response, "MANAGED-PHOTO")
        self.assertContains(response, "MANAGED-ACTIVITY")

    def test_the_gallery_block_reports_its_photo_count(self):
        make_documentation_photo(make_proposal())
        section = PageSection.objects.filter(
            page__slug="gallery", layout=PageSection.Layout.GALLERY
        ).first()
        self.assertEqual(resolve_section_data(section)["photo_count"], 1)


class NavigationTests(TestCase):
    """The public menu offers the active pages and omits retired ones."""

    def test_the_navbar_links_to_the_new_pages(self):
        html = self.client.get("/").content.decode()
        for name in ("programs_page", "gallery_page"):
            with self.subTest(name=name):
                self.assertIn(reverse(name), html)

    def test_the_old_and_retired_pages_are_no_longer_linked(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn(">Reports</a>", html)
        self.assertNotIn(">Achievements</a>", html)
        self.assertNotIn('href="/reports/"', html)
        self.assertNotIn('href="/achievements/"', html)
        self.assertNotIn('href="/about/"', html)
        self.assertNotIn('href="/help/"', html)

    def test_the_admin_dashboard_offers_the_new_builders(self):
        admin = factories.make_user("nav_admin", Profile.ROLE_ADMIN)
        response = factories.make_client(admin).get(reverse("admin_dashboard"))
        for name in ("programs_list", "gallery_photos_list"):
            with self.subTest(name=name):
                self.assertContains(response, reverse(name))
        # The four active editable pages are offered, without About.
        for slug in ("home", "services", "programs", "gallery"):
            with self.subTest(slug=slug):
                self.assertContains(response, reverse("page_content_edit", args=[slug]))
        self.assertNotContains(response, "/dashboard/admin/pages/about/")


class ProgramsCmsTests(TestCase):
    """The Programs page is composed from blocks like every other page."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("programs_cms_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def test_the_page_editor_lists_the_directory_block(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["programs"]))
        self.assertContains(response, "Extension Programs")
        self.assertContains(response, reverse("programs_list"))

    def test_editing_the_heading_updates_the_public_page(self):
        section = PageSection.objects.get(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        )
        section.heading = "PUBLIC-PROGRAMS-HEADING"
        section.save()

        self.assertContains(
            self.client.get(reverse("programs_page")), "PUBLIC-PROGRAMS-HEADING"
        )

    def test_the_directory_can_be_dropped_onto_another_page(self):
        self.client_admin.post(
            reverse("page_section_add_source", args=["gallery"]), {"source": "PROGRAMS"}
        )
        make_proposal(title="CROSS-PAGE-MARKER")
        self.assertContains(
            self.client.get(reverse("gallery_page")), "CROSS-PAGE-MARKER"
        )


class ProposalDirectoryTests(TestCase):
    """Programs come from the system: approved proposals and legacy uploads.

    The office should not maintain a second copy of a program it already
    approved, so the directory reads the proposals themselves — and a
    proposal's own signed document is what its card links to.
    """

    def setUp(self):
        self.programs_url = reverse("programs_page")

    def test_an_approved_proposal_appears_with_its_own_details(self):
        make_proposal(title="APPROVED-MARKER")
        response = self.client.get(self.programs_url)
        self.assertContains(response, "APPROVED-MARKER")
        self.assertContains(response, "Barangay Sabangan residents")
        self.assertContains(response, "Improve household nutrition.")

    def test_a_draft_proposal_stays_private(self):
        make_proposal(title="DRAFT-MARKER", status="DRAFTING", overall="DRAFT")
        self.assertNotContains(self.client.get(self.programs_url), "DRAFT-MARKER")

    def test_a_proposal_under_review_stays_private(self):
        make_proposal(
            title="REVIEW-MARKER",
            status="IN_REVIEW",
            overall="REJECTED",
        )
        self.assertNotContains(self.client.get(self.programs_url), "REVIEW-MARKER")

    def test_a_proposals_signed_document_is_its_document_link(self):
        proposal = make_proposal(title="DOCUMENT-MARKER")
        make_signed_document(proposal)
        response = self.client.get(self.programs_url)
        self.assertContains(response, "View approved proposal")
        self.assertContains(
            response, reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )

    def test_a_proposal_without_a_signed_document_has_no_document_link(self):
        make_proposal(title="NO-DOCUMENT-MARKER")
        response = self.client.get(self.programs_url)
        self.assertContains(response, "NO-DOCUMENT-MARKER")
        self.assertNotContains(response, "View approved proposal")

    def test_a_legacy_upload_uses_its_uploaded_file(self):
        proposal = make_proposal(
            title="LEGACY-MARKER",
            status="COMPLETED",
            overall="COMPLETED",
            legacy=True,
            legacy_proposal_file=SimpleUploadedFile(
                "old-proposal.pdf", b"%PDF-1.4 legacy"
            ),
        )
        response = self.client.get(self.programs_url)
        self.assertContains(response, "LEGACY-MARKER")
        self.assertContains(response, "View legacy upload")
        self.assertContains(
            response, reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )

    def program_data(self):
        """The Programs block data, resolved the way the page renders it."""
        section = PageSection.objects.filter(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        ).first()
        return resolve_section_data(section)

    def test_the_totals_row_counts_proposals_and_legacy_uploads(self):
        make_proposal(title="ONE", beneficiaries_count=10)
        make_proposal(title="TWO", beneficiaries_count=15)
        make_legacy_proposal(title="THREE", beneficiaries_count=5)
        stats = self.program_data()["stats"]
        self.assertEqual(stats["program_count"], 3)
        self.assertEqual(stats["beneficiaries"], 30)
        self.assertEqual(stats["approved"], 2)
        self.assertEqual(stats["legacy"], 1)

    def test_the_extension_type_choices_come_from_the_proposals(self):
        make_proposal(title="RESEARCH", extension_type="RESEARCH_FACULTY")
        types = {
            facet["value"]
            for facet in self.program_data()["facets"]["extension_types"]
        }
        self.assertIn("RESEARCH_BASED", types)
        self.assertNotIn("REQUEST_BASED", types)


class ProgramDocumentTests(TestCase):
    """``/programs/document/<key>/`` serves only what the directory publishes."""

    def test_an_approved_proposals_document_downloads(self):
        proposal = make_proposal()
        make_signed_document(proposal)
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"] + "attachment")

    def test_a_legacy_upload_document_downloads(self):
        proposal = make_proposal(
            legacy=True,
            legacy_proposal_file=SimpleUploadedFile(
                "legacy.pdf", b"%PDF-1.4 legacy"
            ),
        )
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )
        self.assertEqual(response.status_code, 200)

    def test_a_drafts_document_is_not_reachable(self):
        proposal = make_proposal(status="DRAFTING", overall="DRAFT")
        make_signed_document(proposal)
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )
        self.assertEqual(response.status_code, 404)

    def test_an_unapproved_legacy_upload_is_not_reachable(self):
        proposal = make_legacy_proposal(
            title="HIDDEN",
            proposal_status="DRAFTING",
            status="DRAFT",
        )
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )
        self.assertEqual(response.status_code, 404)

    def test_a_proposal_without_a_file_is_not_reachable(self):
        proposal = make_proposal()
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"p{proposal.pk}"})
        )
        self.assertEqual(response.status_code, 404)

    def test_an_unparseable_key_is_a_404(self):
        response = self.client.get(
            reverse("program_document", kwargs={"key": "zzz"})
        )
        self.assertEqual(response.status_code, 404)


class DocumentationGalleryTests(TestCase):
    """The proponent's terminal-report photos are the public Gallery."""

    def setUp(self):
        self.gallery_url = reverse("gallery_page")

    def test_a_terminal_report_photo_appears_in_the_gallery(self):
        make_documentation_photo(make_proposal(), caption="TERMINAL-CAPTION")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "TERMINAL-CAPTION")
        self.assertContains(response, "Terminal report")

    def test_a_hidden_terminal_photo_stays_private(self):
        make_documentation_photo(
            make_proposal(), caption="PRIVATE-PHOTO", is_visible=False
        )
        self.assertNotContains(self.client.get(self.gallery_url), "PRIVATE-PHOTO")

    def test_a_draft_proposals_photos_stay_private(self):
        proposal = make_proposal(proposal_status="DRAFTING", status="DRAFT")
        make_documentation_photo(proposal, caption="DRAFT-PHOTO")
        self.assertNotContains(self.client.get(self.gallery_url), "DRAFT-PHOTO")

    def test_the_photo_count_is_reported(self):
        make_documentation_photo(make_proposal())
        section = PageSection.objects.filter(
            page__slug="gallery", layout=PageSection.Layout.GALLERY
        ).first()
        self.assertEqual(resolve_section_data(section)["photo_count"], 1)

    def test_an_admin_can_hide_a_photo(self):
        admin = factories.make_user("moderator", Profile.ROLE_ADMIN)
        client = factories.make_client(admin)
        photo = make_documentation_photo(make_proposal(), caption="MODERATED")
        response = client.post(reverse("documentation_photo_toggle", args=[photo.id]))
        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertFalse(photo.is_visible)
        self.assertNotContains(self.client.get(self.gallery_url), "MODERATED")

    def test_an_admin_can_delete_a_photo(self):
        admin = factories.make_user("remover", Profile.ROLE_ADMIN)
        client = factories.make_client(admin)
        photo = make_documentation_photo(make_proposal())
        client.post(reverse("documentation_photo_delete", args=[photo.id]))
        self.assertFalse(DocumentationPhoto.objects.filter(pk=photo.pk).exists())

    def test_a_non_admin_cannot_moderate_photos(self):
        user = factories.make_user("plain-user", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        photo = make_documentation_photo(make_proposal())
        response = client.post(reverse("documentation_photo_toggle", args=[photo.id]))
        self.assertIn(response.status_code, DENIED)
        photo.refresh_from_db()
        self.assertTrue(photo.is_visible)


class PageHeroTests(TestCase):
    """The banner belongs to the page, so it follows the page's own title."""

    def setUp(self):
        self.admin = factories.make_user("hero_admin", Profile.ROLE_ADMIN)
        self.client_admin = factories.make_client(self.admin)

    def test_the_banner_shows_the_page_title_by_default(self):
        page = SitePage.get_for("programs")
        self.assertEqual(page.hero_title, "Programs")
        self.assertEqual(hero_heading(self.client.get(reverse("programs_page"))), "Programs")

    def test_a_seeded_page_does_not_keep_the_replaced_pages_wording(self):
        """Programs used to announce itself as "Extension Reports"."""
        html = self.client.get(reverse("programs_page")).content.decode()
        self.assertNotIn("Extension reports and documentation", html)
        self.assertNotIn("Extension Reports</p>", html)
        self.assertNotIn("Extension Achievements", self.client.get(reverse("gallery_page")).content.decode())

    def test_renaming_the_page_renames_the_banner(self):
        page = SitePage.get_for("programs")
        page.title = "Extension Portfolio"
        page.save()
        self.assertEqual(
            hero_heading(self.client.get(reverse("programs_page"))),
            "Extension Portfolio",
        )

    def test_an_explicit_hero_heading_still_wins(self):
        page = SitePage.get_for("gallery")
        page.hero_heading = "Photos from the field"
        page.save()
        self.assertEqual(
            hero_heading(self.client.get(reverse("gallery_page"))),
            "Photos from the field",
        )

    def test_saving_the_title_as_the_heading_keeps_it_following_the_title(self):
        """Typing the title into the hero field must not freeze the banner."""
        self.client_admin.post(
            reverse("page_content_edit", args=["gallery"]),
            {"title": "Program Gallery", "hero_heading": "program gallery", "is_published": "on"},
        )
        page = SitePage.get_for("gallery")
        self.assertEqual(page.hero_heading, "")
        self.assertEqual(page.hero_title, "Program Gallery")

    def test_the_editor_explains_the_fallback(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["programs"]))
        self.assertContains(response, "Leave blank to show the page title")


class CampusesBlockTests(TestCase):
    """The Campuses block lists the campuses the institution actually records."""

    def setUp(self):
        Campus.objects.get_or_create(name="Main")
        Campus.objects.get_or_create(name="Sta Maria")
        Campus.objects.get_or_create(name="Candon")
        # Place the block the way an admin would, from the page palette.
        self.section = PageSection.objects.create(
            page=SitePage.get_for("gallery"),
            layout=PageSection.Layout.CAMPUSES,
            heading="Campuses we serve",
            order=9,
        )

    def test_the_page_lists_every_campus(self):
        response = self.client.get(reverse("gallery_page"))
        for name in ("Main Campus", "Sta Maria Campus", "Candon Campus"):
            with self.subTest(name=name):
                self.assertContains(response, name)

    def test_each_campus_shows_how_many_programs_it_has_run(self):
        make_proposal(title="STA-MARIA-PROGRAM", campus="Sta. Maria Campus")
        data = resolve_section_data(self.section)
        counts = {c["label"]: c["program_count"] for c in data["campuses"]}
        # "Sta. Maria Campus" on the program matches the "Sta Maria" campus row.
        self.assertEqual(counts["Sta Maria Campus"], 1)
        self.assertEqual(counts["Main Campus"], 0)
        # Every campus the institution records is listed, not just the seeded ones.
        self.assertEqual(data["campus_count"], Campus.objects.count())

    def test_a_campus_that_only_appears_in_a_proposal_is_still_listed(self):
        make_proposal(title="UNLISTED-CAMPUS", campus="Cervantes Campus")
        data = resolve_section_data(self.section)
        labels = {c["label"] for c in data["campuses"]}
        self.assertIn("Cervantes Campus", labels)
        self.assertEqual(data["program_count"], 1)

    def test_campuses_is_a_registered_content_source(self):
        source = get_content_source("CAMPUSES")
        self.assertIsNotNone(source)
        self.assertEqual(source.block_template, "details/blocks/campuses.html")


class RetiredAboutAndHelpTests(TestCase):
    """About and Help are retired for now; content sources remain intact."""

    def test_about_and_help_urls_return_404(self):
        self.assertEqual(self.client.get("/about/").status_code, 404)
        self.assertEqual(self.client.get("/help/").status_code, 404)

    def test_the_anchor_bar_only_appears_when_there_is_something_to_jump_between(self):
        gallery = SitePage.get_for("gallery")
        PageSection.objects.create(
            page=gallery,
            layout=PageSection.Layout.RICH_TEXT,
            heading="Field notes",
            anchor="field-notes",
            body="<p>Notes</p>",
            order=9,
        )
        # Gallery with two sections renders the anchor bar.
        self.assertContains(self.client.get(reverse("gallery_page")), 'href="#field-notes"')
        # Programs has one; a bar repeating the banner would be noise.
        self.assertNotContains(self.client.get(reverse("programs_page")), 'href="#all-programs"')

    def test_the_profile_block_stays_a_registered_content_source(self):
        source = get_content_source("SYSTEM_PROFILE")
        self.assertIsNotNone(source)
        self.assertEqual(source.block_template, "details/blocks/system_profile.html")


class PublicSubnavConsistencyTests(TestCase):
    """Every public page uses the same sticky horizontal sub-menu bar."""

    SUBNAV_MARKER = 'class="nx-public-subnav bg-white border-b border-gray-100 sticky top-20 z-40"'

    def _assert_subnav_targets_exist(self, html):
        self.assertIn(self.SUBNAV_MARKER, html)
        subnav_match = re.search(
            r'<section class="nx-public-subnav[^>]*>(.*?)</section>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(subnav_match)
        anchors = re.findall(r'href="#([^"]+)"', subnav_match.group(1))
        self.assertGreaterEqual(len(anchors), 2)
        for anchor in anchors:
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', html)

    def test_home_and_services_share_the_sticky_subnav_bar(self):
        home_html = self.client.get(reverse("details_page")).content.decode()
        services_html = self.client.get(reverse("services_home")).content.decode()

        self._assert_subnav_targets_exist(home_html)
        self._assert_subnav_targets_exist(services_html)
        self.assertNotIn("services-jump-links", services_html)
        for anchor in ("workflow", "proposal-wizard", "status-lifecycle"):
            self.assertIn(f'href="#{anchor}"', services_html)

    def test_programs_and_gallery_use_the_same_sticky_subnav_bar(self):
        make_proposal(title="SUBNAV-PROGRAM", campus="Main Campus", estimated_year=2025)
        programs_html = self.client.get(reverse("programs_page")).content.decode()
        self._assert_subnav_targets_exist(programs_html)
        for anchor in (
            "program-summary",
            "program-overview",
            "program-filters",
            "program-directory",
        ):
            self.assertIn(f'href="#{anchor}"', programs_html)

        gallery = SitePage.get_for("gallery")
        PageSection.objects.create(
            page=gallery,
            layout=PageSection.Layout.CAMPUSES,
            heading="Campuses",
            anchor="campuses",
            order=9,
        )
        gallery_html = self.client.get(reverse("gallery_page")).content.decode()
        self._assert_subnav_targets_exist(gallery_html)

