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

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from details.content_sources import get_content_source
from details.models import (
    ExtensionProgram,
    GalleryPhoto,
    PageSection,
    SitePage,
    resolve_section_data,
)

from . import factories


DENIED = (302, 403)

#: A 1x1 transparent GIF: the smallest valid image Django will accept.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


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

    def test_the_replaced_pages_keep_their_blocks(self):
        """Renaming, rather than deleting, preserved the admin's sections.

        Reports used to hold the Targets block and Achievements the Activities
        block; both must still be on the successor page, below the new block.
        """
        programs = SitePage.get_for("programs")
        gallery = SitePage.get_for("gallery")
        self.assertEqual(
            list(programs.sections.values_list("layout", flat=True)),
            ["PROGRAMS", "TARGETS"],
        )
        self.assertEqual(
            list(gallery.sections.values_list("layout", flat=True)),
            ["GALLERY", "ACTIVITIES"],
        )

    def test_about_has_its_first_sections(self):
        page = SitePage.get_for("about")
        self.assertEqual(
            list(page.sections.values_list("layout", flat=True)),
            ["RICH_TEXT", "CTA"],
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
        ExtensionProgram.objects.create(
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
            document_url="https://example.com/document",
        )

        response = self.client.get(self.programs_url)
        self.assertContains(response, "PROGRAM-MARKER")
        self.assertContains(response, "Main Campus")
        self.assertContains(response, "Dili National High School")
        self.assertContains(response, "September 2025 – February 2026")
        self.assertContains(response, "Improve reading comprehension.")
        self.assertContains(response, 'href="https://example.com/document"')
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
        self.assertContains(response, "No extension programs have been published yet.")

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

    def test_a_url_outside_http_is_rejected(self):
        before = ExtensionProgram.objects.count()
        self.client_admin.post(
            reverse("program_create"),
            self._payload(document_url="javascript:alert(1)"),
        )
        self.assertEqual(ExtensionProgram.objects.count(), before)

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

    def test_a_program_cover_fills_the_gallery_when_no_photo_exists(self):
        """A cover photo already uploaded on the program is not asked for twice."""
        ExtensionProgram.objects.create(
            title="COVER-PROGRAM",
            campus="Main Campus",
            cover_image=SimpleUploadedFile(
                "cover.gif", TINY_GIF, content_type="image/gif"
            ),
        )
        response = self.client.get(self.gallery_url)
        self.assertContains(response, "COVER-PROGRAM")

    def test_adding_a_gallery_photo_retires_the_automatic_cover(self):
        program = ExtensionProgram.objects.create(
            title="COVER-PROGRAM",
            cover_image=SimpleUploadedFile(
                "cover.gif", TINY_GIF, content_type="image/gif"
            ),
        )
        make_photo(program=program, title="REAL-PHOTO")

        response = self.client.get(self.gallery_url)
        self.assertContains(response, "REAL-PHOTO")
        # The cover is no longer added on its own, so the program appears once.
        self.assertEqual(response.content.decode().count("Open photo: COVER-PROGRAM"), 0)

    def test_a_hidden_programs_cover_stays_out_of_the_gallery(self):
        ExtensionProgram.objects.create(
            title="HIDDEN-COVER",
            is_visible=False,
            cover_image=SimpleUploadedFile(
                "cover.gif", TINY_GIF, content_type="image/gif"
            ),
        )
        self.assertNotContains(self.client.get(self.gallery_url), "HIDDEN-COVER")

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
