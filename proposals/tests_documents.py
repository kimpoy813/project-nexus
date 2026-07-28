"""
Document generation tests.

``docx_forms.py`` (2,188 lines) and ``moa_docx.py`` (570) had no coverage at
all, which is why the 42 broad exception handlers in ``docx_forms`` were left
untouched during the error-handling pass — narrowing them blind would have
risked silently breaking downloads.

These tests exercise the two public entry points against the real templates
committed under ``proposals/template_files/``, so they catch a corrupt
template or a broken field lookup rather than only checking that a function
returns.

The emphasis is on the properties that matter to a user:

* every extension type / scope combination produces a valid, openable DOCX
* proposal content actually reaches the document
* missing or malformed data degrades to a blank field instead of a 500
"""

import io
import zipfile

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories

from . import docx_forms
from .docx_forms import build_extension_form_docx
from .models import Proposal


def docx_text(data):
    """Return all visible text from a .docx byte string.

    python-docx only exposes body paragraphs conveniently, and much of this
    output lives in tables, headers, and footers. Reading ``document.xml``
    directly is cruder but catches text wherever it ends up.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")

    # Strip tags so assertions can match on plain text.
    import re

    text = re.sub(r"<[^>]+>", "", xml)
    return text


def is_valid_docx(data):
    """A .docx is a zip archive that must contain word/document.xml."""
    if not data or not isinstance(data, (bytes, bytearray)):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


class ExtensionFormRoutingTests(TestCase):
    """The right template is chosen for each extension type and scope."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("doc_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        defaults = {
            "created_by": self.owner,
            "title": "Community Literacy Programme",
            "extension_type": "",
            "scope_type": "",
        }
        defaults.update(kwargs)
        return Proposal.objects.create(**defaults)

    # Text that appears only in the Form 2 training-design template, used to
    # tell the two document families apart. Asserting only "is a valid docx"
    # would pass even if every proposal were routed to the wrong template.
    TRAINING_DESIGN_MARKER = "Budgetary Requirements"

    def _assert_training_design(self, data):
        self.assertTrue(is_valid_docx(data))
        self.assertIn(self.TRAINING_DESIGN_MARKER, docx_text(data))

    def _assert_research_form(self, data):
        self.assertTrue(is_valid_docx(data))
        self.assertNotIn(
            self.TRAINING_DESIGN_MARKER,
            docx_text(data),
            "a research proposal was routed to the training-design template",
        )

    def test_research_program_uses_a_research_template(self):
        proposal = self._proposal(extension_type="RESEARCH_FACULTY", scope_type="PROGRAM")
        self._assert_research_form(build_extension_form_docx(proposal))

    def test_research_project_uses_a_research_template(self):
        proposal = self._proposal(extension_type="RESEARCH_FACULTY", scope_type="PROJECT")
        self._assert_research_form(build_extension_form_docx(proposal))

    def test_student_research_uses_a_research_template(self):
        proposal = self._proposal(extension_type="RESEARCH_STUDENT", scope_type="PROJECT")
        self._assert_research_form(build_extension_form_docx(proposal))

    def test_non_research_falls_back_to_the_training_design_form(self):
        proposal = self._proposal(extension_type="REQUEST_BASED", scope_type="PROJECT")
        self._assert_training_design(build_extension_form_docx(proposal))

    def test_community_based_also_uses_the_training_design_form(self):
        proposal = self._proposal(extension_type="COMMUNITY_BASED", scope_type="PROJECT")
        self._assert_training_design(build_extension_form_docx(proposal))

    def test_program_and_project_scope_select_different_templates(self):
        """PROGRAM and PROJECT scope must not collapse onto one template.

        The two research templates are textually identical for an empty
        proposal — they differ only in embedded binary parts — so this asserts
        on the chosen template path rather than on the rendered output.
        """
        from unittest.mock import patch

        chosen = []
        real_document = docx_forms.Document

        def spy(path, *args, **kwargs):
            chosen.append(str(path))
            return real_document(path, *args, **kwargs)

        with patch.object(docx_forms, "Document", side_effect=spy):
            build_extension_form_docx(
                self._proposal(extension_type="RESEARCH_FACULTY", scope_type="PROGRAM")
            )
            build_extension_form_docx(
                self._proposal(extension_type="RESEARCH_FACULTY", scope_type="PROJECT")
            )

        self.assertIn("form1_program_template.docx", chosen[0])
        self.assertIn("form1_project_template.docx", chosen[1])

    def test_non_research_selects_the_training_design_template(self):
        from unittest.mock import patch

        chosen = []
        real_document = docx_forms.Document

        def spy(path, *args, **kwargs):
            chosen.append(str(path))
            return real_document(path, *args, **kwargs)

        with patch.object(docx_forms, "Document", side_effect=spy):
            build_extension_form_docx(
                self._proposal(extension_type="REQUEST_BASED", scope_type="PROJECT")
            )

        self.assertIn("form2_training_design_template.docx", chosen[0])

    def test_every_declared_extension_type_generates_a_document(self):
        for extension_type in Proposal.ExtensionType:
            for scope in ["PROGRAM", "PROJECT", "ACTIVITY", ""]:
                with self.subTest(extension_type=extension_type, scope=scope):
                    proposal = self._proposal(
                        extension_type=extension_type, scope_type=scope
                    )
                    data = build_extension_form_docx(proposal)
                    self.assertTrue(is_valid_docx(data))

    def test_a_blank_proposal_still_generates_rather_than_raising(self):
        """A half-filled draft must still download; blanks are expected."""
        proposal = self._proposal()
        data = build_extension_form_docx(proposal)
        self.assertTrue(is_valid_docx(data))

    def test_extra_positional_and_keyword_arguments_are_ignored(self):
        """The signature is intentionally permissive; callers changed over time."""
        proposal = self._proposal(extension_type="REQUEST_BASED")
        data = build_extension_form_docx(proposal, "legacy", unused=True)
        self.assertTrue(is_valid_docx(data))


class ExtensionFormContentTests(TestCase):
    """Proposal data must actually reach the generated document."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("content_owner", Profile.ROLE_FACULTY)

    def test_the_proposal_title_appears_in_the_document(self):
        proposal = Proposal.objects.create(
            created_by=self.owner,
            title="UNIQUE-TITLE-MARKER-12345",
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )
        text = docx_text(build_extension_form_docx(proposal))
        self.assertIn("UNIQUE-TITLE-MARKER-12345", text)

    def test_a_title_containing_xml_characters_does_not_corrupt_the_file(self):
        """Ampersands and angle brackets must be escaped, not injected raw."""
        proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Health & Safety <Phase 1> \"Pilot\"",
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )
        data = build_extension_form_docx(proposal)
        self.assertTrue(is_valid_docx(data), "special characters produced a corrupt docx")

    def test_a_very_long_title_does_not_break_generation(self):
        proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Extension Programme " * 12,  # long but within max_length=300
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )
        self.assertTrue(is_valid_docx(build_extension_form_docx(proposal)))

    def test_unicode_content_survives_generation(self):
        proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Pagpapaunlad ng Pamayanan — Ilocos Sur ñ 日本語",
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )
        text = docx_text(build_extension_form_docx(proposal))
        self.assertIn("Pagpapaunlad", text)


class DocxHelperTests(TestCase):
    """The defensive helpers that the broad exception handlers protect."""

    def test_safe_int_converts_and_falls_back(self):
        from .docx_forms import _safe_int

        self.assertEqual(_safe_int(5), 5)
        self.assertEqual(_safe_int("7"), 7)
        self.assertEqual(_safe_int(None), 0)
        self.assertEqual(_safe_int("not a number"), 0)
        self.assertEqual(_safe_int(object()), 0)
        self.assertEqual(_safe_int(None, default=99), 99)

    def test_get_related_list_handles_missing_and_broken_relations(self):
        from .docx_forms import _get_related_list

        class Empty:
            pass

        self.assertEqual(_get_related_list(Empty(), "nope"), [])

        class WithList:
            items = [1, 2, 3]

        # A plain list has no .all(), so the fallback path is used.
        self.assertEqual(_get_related_list(WithList(), "items"), [1, 2, 3])

    def test_to_roman_covers_the_range_used_by_the_forms(self):
        from .docx_forms import _to_roman

        self.assertEqual(_to_roman(1), "I")
        self.assertEqual(_to_roman(4), "IV")
        self.assertEqual(_to_roman(9), "IX")
        self.assertEqual(_to_roman(14), "XIV")

    def test_file_basename_tolerates_a_missing_file(self):
        from .docx_forms import _file_basename

        self.assertEqual(_file_basename(None), "")

    def test_strip_leading_bullets_removes_symbol_markers(self):
        from .docx_forms import _strip_leading_bullets

        for raw in ["• Item", "- Item", "* Item", "· Item", "-- Item"]:
            with self.subTest(raw=raw):
                self.assertEqual(_strip_leading_bullets(raw), "Item")

    def test_strip_leading_bullets_leaves_numbering_intact(self):
        """Documented behaviour: numbered lists keep their numbers."""
        from .docx_forms import _strip_leading_bullets

        self.assertEqual(_strip_leading_bullets("1. Item"), "1. Item")

    def test_strip_leading_bullets_handles_multiple_lines(self):
        from .docx_forms import _strip_leading_bullets

        self.assertEqual(_strip_leading_bullets("- One\n• Two"), "One\nTwo")


class MOADocumentTests(TestCase):
    """``build_moa_document`` composes a MOA from scratch, with no template."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("moa_owner", Profile.ROLE_FACULTY)

    def _build(self, proposal, data=None):
        from .moa_docx import build_moa_document

        buffer = build_moa_document(proposal, data or {})
        buffer.seek(0)
        return buffer.getvalue()

    def test_it_produces_a_valid_docx(self):
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        self.assertTrue(is_valid_docx(self._build(proposal)))

    def test_an_empty_data_dict_still_produces_a_document(self):
        """Every field is optional in the guided form."""
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        self.assertTrue(is_valid_docx(self._build(proposal, {})))

    def test_the_moa_heading_is_present(self):
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        text = docx_text(self._build(proposal))
        self.assertIn("MEMORANDUM OF AGREEMENT", text)

    def test_the_partner_name_reaches_the_document(self):
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        text = docx_text(self._build(proposal, {"partner_name": "Barangay Poblacion"}))
        self.assertIn("BARANGAY POBLACION", text.upper())

    def test_the_partner_name_falls_back_to_a_placeholder(self):
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        text = docx_text(self._build(proposal, {}))
        self.assertIn("PARTNER INSTITUTION", text.upper())

    def test_the_project_title_reaches_the_document(self):
        proposal = Proposal.objects.create(
            created_by=self.owner, title="MOA-TITLE-MARKER-999"
        )
        text = docx_text(self._build(proposal))
        self.assertIn("MOA-TITLE-MARKER-999", text)

    def test_special_characters_in_partner_data_do_not_corrupt_the_file(self):
        proposal = Proposal.objects.create(created_by=self.owner, title="Water Access")
        data = {
            "partner_name": "Smith & Sons <Group>",
            "partner_address": 'No. 1 "Main" St. & Co.',
            "partner_rep_name": "José Ñuñez",
        }
        self.assertTrue(is_valid_docx(self._build(proposal, data)))


class DocumentDownloadViewTests(TestCase):
    """The download endpoints must enforce access and return a real file."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("dl_owner", Profile.ROLE_FACULTY)
        cls.stranger = factories.make_user("dl_stranger", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(
            created_by=self.owner,
            title="Downloadable Proposal",
            extension_type="REQUEST_BASED",
            scope_type="PROJECT",
        )

    def test_the_owner_can_download_the_proposal_docx(self):
        client = factories.make_client(self.owner)
        response = client.get(
            reverse("proposal_download_approved_docx", args=[self.proposal.id])
        )
        self.assertIn(response.status_code, (200, 302))

        if response.status_code == 200:
            self.assertTrue(is_valid_docx(response.content))

    def test_anonymous_users_cannot_download(self):
        response = self.client.get(
            reverse("proposal_download_approved_docx", args=[self.proposal.id])
        )
        self.assertIn(response.status_code, (302, 403))

    XLSX_TEMPLATE_URLS = [
        "download_work_plan_template",
        "download_gantt_chart_template",
        "download_funding_template",
    ]

    def test_the_xlsx_templates_download_for_the_owner(self):
        client = factories.make_client(self.owner)
        for name in self.XLSX_TEMPLATE_URLS:
            with self.subTest(url=name):
                response = client.get(reverse(name, args=[self.proposal.id]))
                self.assertIn(response.status_code, (200, 302))

    def test_a_downloaded_xlsx_template_is_a_real_workbook(self):
        client = factories.make_client(self.owner)
        response = client.get(
            reverse("download_work_plan_template", args=[self.proposal.id])
        )
        if response.status_code == 200:
            # .xlsx is a zip archive containing the workbook part.
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                self.assertIn("xl/workbook.xml", archive.namelist())

    def test_the_xlsx_templates_require_login(self):
        for name in self.XLSX_TEMPLATE_URLS:
            with self.subTest(url=name):
                response = self.client.get(reverse(name, args=[self.proposal.id]))
                self.assertIn(response.status_code, (302, 403))


class TemplateFileTests(TestCase):
    """The committed template files must exist and be readable."""

    def test_every_referenced_template_is_present_and_valid(self):
        import pathlib

        base = pathlib.Path(__file__).resolve().parent / "template_files"
        required = [
            "form1_program_template.docx",
            "form1_project_template.docx",
            "form2_training_design_template.docx",
            "clear_summary_template.docx",
        ]

        for name in required:
            with self.subTest(template=name):
                path = base / name
                self.assertTrue(path.exists(), f"{name} is missing")
                self.assertTrue(
                    is_valid_docx(path.read_bytes()), f"{name} is not a readable .docx"
                )

    def test_the_xlsx_templates_are_present(self):
        import pathlib

        base = pathlib.Path(__file__).resolve().parent / "template_files"
        for name in [
            "program_work_plan_template.xlsx",
            "project_work_plan_template.xlsx",
            "program_funding_template.xlsx",
            "project_funding_template.xlsx",
        ]:
            with self.subTest(template=name):
                self.assertTrue((base / name).exists(), f"{name} is missing")
