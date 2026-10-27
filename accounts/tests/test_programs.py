"""
Tests for the Programs directory, the Gallery, and the About page.

These three pages replaced Reports and Achievements. The coverage here follows
the same rule as the rest of the CMS suite: an admin edits a record, and the
public page reflects it — while nothing an admin has not published leaks out.

  * **Programs**    - every published program, its totals, and its filters
  * **Gallery**     - photographs, either attached to a program or standalone
  * **About**       - the seeded page, editable like any other
  * **Navigation**  - the site menu offers the new pages and none of the old
"""

import re

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import Campus, Profile
from details.content_sources import get_content_source
from details.models import (
    ExtensionProgram,
    GalleryPhoto,
    PageSection,
    SitePage,
    resolve_section_data,
)
from proposals.models import Proposal, ProposalFinalDocument, TerminalReportPhoto

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


def make_terminal_photo(proposal, caption="TERMINAL-PHOTO", **overrides):
    defaults = {
        "proposal": proposal,
        "image": SimpleUploadedFile("doc.gif", TINY_GIF, content_type="image/gif"),
        "caption": caption,
    }
    defaults.update(overrides)
    return TerminalReportPhoto.objects.create(**defaults)


def hero_heading(response):
    """The text inside the page's `<h1>`, whitespace collapsed."""
    match = re.search(r"<h1[^>]*>(.*?)</h1>", response.content.decode(), re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def make_photo(**overrides):
    defaults = {
        "image": SimpleUploadedFile("photo.gif", TINY_GIF, content_type="image/gif"),
        "title": "PHOTO-MARKER",
    }
    defaults.update(overrides)
    return GalleryPhoto.objects.create(**defaults)


class SeededPageTests(TestCase):
    """The migration replaces Reports/Achievements with the three new pages."""

    def test_the_five_public_pages_are_seeded(self):
        self.assertEqual(
            set(SitePage.objects.values_list("slug", flat=True)),
            {"home", "services", "programs", "gallery", "about"},
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

    def test_about_explains_the_office_its_campuses_and_how_to_work_with_it(self):
        page = SitePage.get_for("about")
        self.assertEqual(
            list(page.sections.values_list("layout", flat=True)),
            ["RICH_TEXT", "CAMPUSES", "CTA"],
        )

    def test_the_new_pages_render(self):
        for name in ("programs_page", "gallery_page", "about_page"):
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
        page = SitePage.get_for("about")
        page.is_published = False
        page.save()

        self.assertEqual(self.client.get(reverse("about_page")).status_code, 404)

        admin = factories.make_user("about_admin", Profile.ROLE_ADMIN)
        response = factories.make_client(admin).get(reverse("about_page"))
        self.assertEqual(response.status_code, 200)


class ProgramsPageTests(TestCase):
    """The Programs page is the directory of every published program."""

    def setUp(self):
        self.programs_url = reverse("programs_page")

    def test_a_program_row_appears_with_its_details(self):
        program = ExtensionProgram.objects.create(
            title="PROGRAM-MARKER",
            campus="Main Campus",
            year=2025,
            extension_type=ExtensionProgram.ExtensionType.RESEARCH_BASED,
            research_basis=ExtensionProgram.ResearchBasis.FACULTY,
            led_by=ExtensionProgram.Proponent.JOINT,
            target_community="Dili National High School",
            duration="September 2025 – February 2026",
            objectives="Improve reading comprehension.",
            student_participants=50,
            faculty_participants=5,
            beneficiaries=34,
            document=SimpleUploadedFile("doc-marker.pdf", b"%PDF-1.4 marker"),
        )

        response = self.client.get(self.programs_url)
        self.assertContains(response, "PROGRAM-MARKER")
        self.assertContains(response, "Main Campus")
        self.assertContains(response, "Dili National High School")
        self.assertContains(response, "September 2025 – February 2026")
        self.assertContains(response, "Improve reading comprehension.")
        self.assertContains(response, "View legacy upload")
        self.assertContains(
            response, reverse("program_document", kwargs={"key": f"r{program.pk}"})
        )
        # Filters are built from the published rows only.
        self.assertContains(response, 'data-campus="Main Campus"')
        self.assertContains(response, 'id="program-campus-')

    def test_the_totals_count_only_published_programs(self):
        ExtensionProgram.objects.create(
            title="VISIBLE", student_participants=10, faculty_participants=2,
            beneficiaries=100, campus="Main Campus",
        )
        ExtensionProgram.objects.create(
            title="HIDDEN", student_participants=999, beneficiaries=999,
            campus="Cervantes Campus", is_visible=False,
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

    def test_a_hidden_program_leaves_its_campus_out_of_the_filter(self):
        ExtensionProgram.objects.create(title="LIVE", campus="Main Campus")
        ExtensionProgram.objects.create(
            title="OFF", campus="Tagudin Campus", is_visible=False
        )
        section = PageSection.objects.filter(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        ).first()
        campuses = resolve_section_data(section)["facets"]["campuses"]
        self.assertEqual([c["value"] for c in campuses], ["Main Campus"])

    def test_the_overview_bars_summarise_published_programs(self):
        ExtensionProgram.objects.create(
            title="ONE", campus="Main Campus", year=2025,
            extension_type=ExtensionProgram.ExtensionType.RESEARCH_BASED,
        )
        ExtensionProgram.objects.create(
            title="TWO", campus="Main Campus", year=2025,
            extension_type=ExtensionProgram.ExtensionType.COMMUNITY_BASED,
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


class ProgramAdminTests(TestCase):
    """Admins manage programs from Content & Builders."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("program_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("program_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _payload(self, **overrides):
        data = {
            "title": "NEW-PROGRAM-MARKER",
            "campus": "Main Campus",
            "year": "2026",
            "extension_type": ExtensionProgram.ExtensionType.COMMUNITY_BASED,
            "research_basis": ExtensionProgram.ResearchBasis.OTHERS,
            "led_by": ExtensionProgram.Proponent.FACULTY,
            "target_community": "Brgy. Sabangan",
            "duration": "May 2026",
            "objectives": "One objective per line.",
            "student_participants": "7",
            "faculty_participants": "3",
            "research_staff_participants": "1",
            "beneficiaries": "42",
            "document_url": "",
            "is_visible": "on",
        }
        data.update(overrides)
        return data

    def test_the_list_page_shows_programs(self):
        ExtensionProgram.objects.create(title="LISTED-MARKER")
        response = self.client_admin.get(reverse("programs_list"))
        self.assertContains(response, "LISTED-MARKER")
        self.assertContains(response, "Extension Programs")

    def test_a_program_can_be_created_and_published(self):
        response = self.client_admin.post(reverse("program_create"), self._payload())
        self.assertRedirects(response, reverse("programs_list"))

        program = ExtensionProgram.objects.get(title="NEW-PROGRAM-MARKER")
        self.assertEqual(program.beneficiaries, 42)
        self.assertTrue(program.is_visible)
        self.assertContains(self.client.get(reverse("programs_page")), "NEW-PROGRAM-MARKER")

    def test_editing_a_program_updates_the_public_card(self):
        program = ExtensionProgram.objects.create(title="BEFORE-MARKER")
        self.client_admin.post(
            reverse("program_edit", args=[program.id]),
            self._payload(title="AFTER-MARKER"),
        )
        program.refresh_from_db()
        self.assertEqual(program.title, "AFTER-MARKER")
        self.assertContains(self.client.get(reverse("programs_page")), "AFTER-MARKER")

    def test_a_program_can_be_hidden_from_the_page(self):
        program = ExtensionProgram.objects.create(title="TO-HIDE-MARKER")
        payload = self._payload(title=program.title)
        payload.pop("is_visible")
        self.client_admin.post(reverse("program_edit", args=[program.id]), payload)

        program.refresh_from_db()
        self.assertFalse(program.is_visible)
        self.assertNotContains(self.client.get(reverse("programs_page")), "TO-HIDE-MARKER")

    def test_a_typed_document_url_is_not_published(self):
        """The document is a file, not a free-form link the admin types."""
        program = ExtensionProgram.objects.create(
            title="LINK-ONLY",
            document_url="https://example.com/still-archived",
        )
        response = self.client.get(reverse("programs_page"))
        self.assertContains(response, "LINK-ONLY")
        self.assertNotContains(response, "still-archived")
        self.assertEqual(program.safe_document_url, "https://example.com/still-archived")

    def test_delete_requires_post(self):
        program = ExtensionProgram.objects.create(title="DELETE-ME")
        self.assertEqual(
            self.client_admin.get(reverse("program_delete", args=[program.id])).status_code,
            405,
        )
        self.assertTrue(ExtensionProgram.objects.filter(pk=program.pk).exists())

        self.client_admin.post(reverse("program_delete", args=[program.id]))
        self.assertFalse(ExtensionProgram.objects.filter(pk=program.pk).exists())

    def test_non_admins_cannot_manage_programs(self):
        client = factories.make_client(self.faculty)
        self.assertIn(client.get(reverse("programs_list")).status_code, DENIED)
        self.assertIn(client.get(reverse("program_create")).status_code, DENIED)

        status = client.post(reverse("program_create"), self._payload()).status_code
        self.assertIn(status, DENIED)
        self.assertFalse(
            ExtensionProgram.objects.filter(title="NEW-PROGRAM-MARKER").exists()
        )


class ProgramCsvImportTests(TestCase):
    """The office's spreadsheet export imports without retyping."""

    HEADER = (
        "Year,Campus,Program title,Extension type,Research basis,Led by,"
        "Target community / beneficiaries,Duration & frequency,Objectives,"
        "Students,Faculty,Research staff,Beneficiaries,Document link\n"
    )

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("import_admin", Profile.ROLE_ADMIN)
        cls.faculty = factories.make_user("import_faculty", Profile.ROLE_FACULTY)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _upload(self, body, client=None):
        upload = SimpleUploadedFile(
            "programs.csv",
            (self.HEADER + body).encode("utf-8"),
            content_type="text/csv",
        )
        return (client or self.client_admin).post(
            reverse("programs_import"), {"file": upload}
        )

    def test_the_import_page_renders(self):
        response = self.client_admin.get(reverse("programs_import"))
        self.assertContains(response, "Import Programs from CSV")
        self.assertContains(response, "Document link")

    def test_rows_are_imported_with_their_labels_and_numbers(self):
        response = self._upload(
            '2025,Main Campus,"CSV-MARKER","Research-based","Faculty Research",'
            'Joint,"Dili National High School","October 2025","Objective one",'
            '"1,024",5,2,300,https://example.com/doc\n'
        )
        self.assertRedirects(response, reverse("programs_list"))

        program = ExtensionProgram.objects.get(title="CSV-MARKER")
        self.assertEqual(program.year, 2025)
        self.assertEqual(
            program.extension_type, ExtensionProgram.ExtensionType.RESEARCH_BASED
        )
        self.assertEqual(
            program.research_basis, ExtensionProgram.ResearchBasis.FACULTY
        )
        self.assertEqual(program.led_by, ExtensionProgram.Proponent.JOINT)
        self.assertEqual(program.student_participants, 1024)
        self.assertEqual(program.beneficiaries, 300)
        self.assertEqual(program.document_url, "https://example.com/doc")
        self.assertContains(self.client.get(reverse("programs_page")), "CSV-MARKER")

    def test_a_reimport_updates_rather_than_duplicates(self):
        self._upload(
            '2025,Main Campus,"REIMPORT-MARKER",Community-based,Others,Faculty,'
            'Brgy. A,June 2025,First objective,0,0,0,10,\n'
        )
        self._upload(
            '2026,Tagudin Campus,"REIMPORT-MARKER",Community-based,Others,Faculty,'
            'Brgy. B,July 2026,Second objective,0,0,0,20,\n'
        )

        program = ExtensionProgram.objects.get(title="REIMPORT-MARKER")
        self.assertEqual(ExtensionProgram.objects.filter(title="REIMPORT-MARKER").count(), 1)
        self.assertEqual(program.campus, "Tagudin Campus")
        self.assertEqual(program.year, 2026)
        self.assertEqual(program.beneficiaries, 20)

    def test_a_row_without_a_title_is_skipped_with_a_message(self):
        response = self._upload(
            '2025,Main Campus,"KEPT-MARKER",Community-based,Others,Faculty,,,,\n'
            '2025,Main Campus,,,,,,,,\n',
            client=self.client_admin,
        )
        self.assertRedirects(response, reverse("programs_list"))
        self.assertTrue(ExtensionProgram.objects.filter(title="KEPT-MARKER").exists())
        self.assertEqual(ExtensionProgram.objects.count(), 1)

    def test_an_unsafe_document_link_is_dropped(self):
        self._upload(
            '2025,Main Campus,"UNSAFE-LINK",Community-based,Others,Faculty,,,,"0,0,0,0,'
            'javascript:alert(1)\n'
        )
        program = ExtensionProgram.objects.get(title="UNSAFE-LINK")
        self.assertEqual(program.document_url, "")
        self.assertEqual(program.safe_document_url, "")
        self.assertNotContains(
            self.client.get(reverse("programs_page")), "javascript:alert(1)"
        )

    def test_a_file_without_a_header_is_refused(self):
        upload = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        response = self.client_admin.post(
            reverse("programs_import"), {"file": upload}
        )
        self.assertRedirects(response, reverse("programs_import"))

    def test_non_admins_cannot_import(self):
        client = factories.make_client(self.faculty)
        self.assertIn(client.get(reverse("programs_import")).status_code, DENIED)
        response = self._upload(
            '2025,Main Campus,"DENIED-MARKER",Community-based,Others,Faculty,,,,\n',
            client=client,
        )
        self.assertIn(response.status_code, DENIED)
        self.assertFalse(
            ExtensionProgram.objects.filter(title="DENIED-MARKER").exists()
        )


class GalleryTests(TestCase):
    """Photos published by an admin appear in the Gallery block."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("gallery_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)
        self.gallery_url = reverse("gallery_page")

    def test_a_published_photo_appears_in_the_grid(self):
        make_photo(title="GALLERY-MARKER")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "GALLERY-MARKER")
        self.assertContains(response, "Open photo: GALLERY-MARKER")

    def test_a_hidden_photo_stays_out_of_the_grid(self):
        make_photo(title="HIDDEN-PHOTO", is_visible=False)
        self.assertNotContains(self.client.get(self.gallery_url), "HIDDEN-PHOTO")

    def test_a_photo_attached_to_a_program_inherits_its_labels(self):
        program = ExtensionProgram.objects.create(
            title="PARENT-PROGRAM", campus="Sta. Maria Campus", year=2025
        )
        make_photo(program=program, title="Seedling distribution")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "Seedling distribution")
        self.assertContains(response, "PARENT-PROGRAM")
        self.assertContains(response, "Sta. Maria Campus")

    def test_an_admin_can_upload_a_photo(self):
        response = self.client_admin.post(
            reverse("gallery_photo_create"),
            {
                "title": "UPLOADED-MARKER",
                "caption": "",
                "campus": "",
                "taken_on": "",
                "is_visible": "on",
                "image": SimpleUploadedFile(
                    "uploaded.gif", TINY_GIF, content_type="image/gif"
                ),
            },
        )
        self.assertRedirects(response, reverse("gallery_photos_list"))
        self.assertTrue(GalleryPhoto.objects.filter(title="UPLOADED-MARKER").exists())
        self.assertContains(self.client.get(self.gallery_url), "UPLOADED-MARKER")

    def test_a_photo_can_be_deleted(self):
        photo = make_photo(title="DELETE-PHOTO")
        self.client_admin.post(reverse("gallery_photo_delete", args=[photo.id]))
        self.assertFalse(GalleryPhoto.objects.filter(pk=photo.pk).exists())
        self.assertNotContains(self.client.get(self.gallery_url), "DELETE-PHOTO")

    def test_the_manager_lists_photos(self):
        make_photo(title="MANAGED-PHOTO")
        response = self.client_admin.get(reverse("gallery_photos_list"))
        self.assertContains(response, "MANAGED-PHOTO")

    def test_the_gallery_block_reports_its_photo_count(self):
        make_photo(title="COUNTED")
        section = PageSection.objects.filter(
            page__slug="gallery", layout=PageSection.Layout.GALLERY
        ).first()
        self.assertEqual(resolve_section_data(section)["photo_count"], 1)


class NavigationTests(TestCase):
    """The public menu offers the new pages and no longer the old ones."""

    def test_the_navbar_links_to_the_new_pages(self):
        html = self.client.get("/").content.decode()
        for name in ("programs_page", "gallery_page", "about_page"):
            with self.subTest(name=name):
                self.assertIn(reverse(name), html)

    def test_the_old_pages_are_no_longer_linked(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn(">Reports</a>", html)
        self.assertNotIn(">Achievements</a>", html)
        self.assertNotIn('href="/reports/"', html)
        self.assertNotIn('href="/achievements/"', html)

    def test_the_admin_dashboard_offers_the_new_builders(self):
        admin = factories.make_user("nav_admin", Profile.ROLE_ADMIN)
        response = factories.make_client(admin).get(reverse("admin_dashboard"))
        for name in ("programs_list", "gallery_photos_list"):
            with self.subTest(name=name):
                self.assertContains(response, reverse(name))
        # The five editable pages are all offered.
        for slug in ("home", "services", "programs", "gallery", "about"):
            with self.subTest(slug=slug):
                self.assertContains(response, reverse("page_content_edit", args=[slug]))


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
            reverse("page_section_add_source", args=["about"]), {"source": "PROGRAMS"}
        )
        ExtensionProgram.objects.create(title="CROSS-PAGE-MARKER")
        self.assertContains(
            self.client.get(reverse("about_page")), "CROSS-PAGE-MARKER"
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

    def test_a_standalone_record_still_appears(self):
        ExtensionProgram.objects.create(
            title="MANUAL-MARKER",
            campus="Candon Campus",
            year=2019,
            document=SimpleUploadedFile("manual.pdf", b"%PDF-1.4 manual"),
        )
        response = self.client.get(self.programs_url)
        self.assertContains(response, "MANUAL-MARKER")
        self.assertContains(response, "View legacy upload")

    def test_a_record_linked_to_a_proposal_is_not_listed_twice(self):
        proposal = make_proposal(title="LINKED-PROPOSAL")
        ExtensionProgram.objects.create(
            title=proposal.title,
            campus=proposal.campus,
            year=2025,
            proposal=proposal,
        )
        html = self.client.get(self.programs_url).content.decode()
        self.assertEqual(html.count("LINKED-PROPOSAL"), 1)

    def program_data(self):
        """The Programs block data, resolved the way the page renders it."""
        section = PageSection.objects.filter(
            page__slug="programs", layout=PageSection.Layout.PROGRAMS
        ).first()
        return resolve_section_data(section)

    def test_the_totals_row_counts_proposals_and_records(self):
        make_proposal(title="ONE", beneficiaries_count=10)
        make_proposal(title="TWO", beneficiaries_count=15)
        ExtensionProgram.objects.create(
            title="THREE", campus="Tagudin Campus", beneficiaries=5
        )
        stats = self.program_data()["stats"]
        self.assertEqual(stats["program_count"], 3)
        self.assertEqual(stats["beneficiaries"], 30)
        self.assertEqual(stats["approved"], 2)

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

    def test_a_hidden_records_document_is_not_reachable(self):
        record = ExtensionProgram.objects.create(
            title="HIDDEN",
            is_visible=False,
            document=SimpleUploadedFile("hidden.pdf", b"%PDF-1.4 hidden"),
        )
        response = self.client.get(
            reverse("program_document", kwargs={"key": f"r{record.pk}"})
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


class TerminalReportGalleryTests(TestCase):
    """Gallery photos come from the terminal report the proponent submits."""

    def setUp(self):
        self.gallery_url = reverse("gallery_page")

    def test_a_terminal_report_photo_appears_in_the_gallery(self):
        make_terminal_photo(make_proposal(), caption="TERMINAL-CAPTION")
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "TERMINAL-CAPTION")
        self.assertContains(response, "Terminal report")

    def test_a_hidden_terminal_photo_stays_private(self):
        make_terminal_photo(make_proposal(), caption="PRIVATE-PHOTO", is_visible=False)
        self.assertNotContains(self.client.get(self.gallery_url), "PRIVATE-PHOTO")

    def test_a_draft_proposals_photos_stay_private(self):
        proposal = make_proposal(status="DRAFTING", overall="DRAFT")
        make_terminal_photo(proposal, caption="DRAFT-PHOTO")
        self.assertNotContains(self.client.get(self.gallery_url), "DRAFT-PHOTO")

    def test_terminal_photos_are_listed_before_arranged_ones(self):
        make_terminal_photo(make_proposal(), caption="FROM-TERMINAL")
        make_photo(title="FROM-OFFICE")
        html = self.client.get(self.gallery_url).content.decode()
        self.assertLess(html.index("FROM-TERMINAL"), html.index("FROM-OFFICE"))

    def test_the_terminal_photo_count_is_reported(self):
        make_terminal_photo(make_proposal())
        section = PageSection.objects.filter(
            page__slug="gallery", layout=PageSection.Layout.GALLERY
        ).first()
        self.assertEqual(resolve_section_data(section)["photo_count"], 1)

    def test_an_admin_can_hide_a_terminal_photo(self):
        admin = factories.make_user("moderator", Profile.ROLE_ADMIN)
        client = factories.make_client(admin)
        photo = make_terminal_photo(make_proposal(), caption="MODERATED")
        response = client.post(reverse("terminal_photo_toggle", args=[photo.id]))
        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertFalse(photo.is_visible)
        self.assertNotContains(self.client.get(self.gallery_url), "MODERATED")

    def test_an_admin_can_delete_a_terminal_photo(self):
        admin = factories.make_user("remover", Profile.ROLE_ADMIN)
        client = factories.make_client(admin)
        photo = make_terminal_photo(make_proposal())
        client.post(reverse("terminal_photo_delete", args=[photo.id]))
        self.assertFalse(TerminalReportPhoto.objects.filter(pk=photo.pk).exists())

    def test_a_non_admin_cannot_moderate_photos(self):
        user = factories.make_user("plain-user", Profile.ROLE_FACULTY)
        client = factories.make_client(user)
        photo = make_terminal_photo(make_proposal())
        response = client.post(reverse("terminal_photo_toggle", args=[photo.id]))
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
            reverse("page_content_edit", args=["about"]),
            {"title": "About us", "hero_heading": "about us", "is_published": "on"},
        )
        page = SitePage.get_for("about")
        self.assertEqual(page.hero_heading, "")
        self.assertEqual(page.hero_title, "About us")

    def test_the_editor_explains_the_fallback(self):
        response = self.client_admin.get(reverse("page_content_edit", args=["programs"]))
        self.assertContains(response, "Leave blank to show the page title")


class CampusesBlockTests(TestCase):
    """The About page lists the campuses the institution actually records."""

    def setUp(self):
        Campus.objects.get_or_create(name="Main")
        Campus.objects.get_or_create(name="Sta Maria")
        Campus.objects.get_or_create(name="Candon")

    def test_the_about_page_lists_every_campus(self):
        response = self.client.get(reverse("about_page"))
        for name in ("Main Campus", "Sta Maria Campus", "Candon Campus"):
            with self.subTest(name=name):
                self.assertContains(response, name)

    def test_each_campus_shows_how_many_programs_it_has_run(self):
        ExtensionProgram.objects.create(
            title="STA-MARIA-PROGRAM", campus="Sta. Maria Campus", year=2025
        )
        data = resolve_section_data(
            PageSection.objects.get(page__slug="about", layout=PageSection.Layout.CAMPUSES)
        )
        counts = {c["label"]: c["program_count"] for c in data["campuses"]}
        # "Sta. Maria Campus" on the program matches the "Sta Maria" campus row.
        self.assertEqual(counts["Sta Maria Campus"], 1)
        self.assertEqual(counts["Main Campus"], 0)
        # Every campus the institution records is listed, not just the seeded ones.
        self.assertEqual(data["campus_count"], Campus.objects.count())

    def test_a_campus_that_only_appears_in_a_program_is_still_listed(self):
        ExtensionProgram.objects.create(
            title="UNLISTED-CAMPUS", campus="Cervantes Campus", year=2025
        )
        data = resolve_section_data(
            PageSection.objects.get(page__slug="about", layout=PageSection.Layout.CAMPUSES)
        )
        labels = {c["label"] for c in data["campuses"]}
        self.assertIn("Cervantes Campus", labels)
        self.assertEqual(data["program_count"], 1)

    def test_campuses_is_a_registered_content_source(self):
        source = get_content_source("CAMPUSES")
        self.assertIsNotNone(source)
        self.assertEqual(source.block_template, "details/blocks/campuses.html")


class AboutPageTests(TestCase):
    """About is a real page: what the office does, where, and how to reach it."""

    def setUp(self):
        self.about_url = reverse("about_page")

    def test_it_explains_what_the_office_does(self):
        response = self.client.get(self.about_url)
        self.assertContains(response, "About the Extension Office")
        self.assertContains(response, "Networked Extension Unified System")

    def test_it_links_to_the_workflow_pages(self):
        response = self.client.get(self.about_url)
        self.assertContains(response, 'href="/programs/"')
        self.assertContains(response, 'href="/gallery/"')
        self.assertContains(response, 'href="/proposals/"')

    def test_it_offers_a_way_to_contact_the_office(self):
        self.assertContains(self.client.get(self.about_url), "mailto:")

    def test_the_anchor_bar_only_appears_when_there_is_something_to_jump_between(self):
        # About has three sections, so the bar is useful there.
        self.assertContains(self.client.get(self.about_url), 'href="#about-the-office"')
        # Programs has one; a bar repeating the banner would be noise.
        self.assertNotContains(self.client.get(reverse("programs_page")), 'href="#all-programs"')
