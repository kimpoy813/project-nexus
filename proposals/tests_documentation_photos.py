"""Documentation photos submitted with the terminal report.

The Gallery is fed by the workflow, not by a separate upload screen: a
proponent files the documentation photos with the terminal report at "Final
Evaluation and Documentation", and those photos become the public gallery.
These tests pin that contract — who may upload, what is accepted, and what a
stranger may not do.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.tests import factories
from .models import Proposal, TerminalReportPhoto


#: A 1x1 transparent GIF: the smallest valid image Django will accept.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def photo(name="doc.gif", content_type="image/gif"):
    return SimpleUploadedFile(name, TINY_GIF, content_type=content_type)


class DocumentationPhotoUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.owner_client = factories.faculty("doc_owner")
        cls.stranger, cls.stranger_client = factories.faculty("doc_stranger")
        cls.director, cls.director_client = factories.director("doc_director")
        cls.proposal = Proposal.objects.create(
            created_by=cls.owner,
            title="Community seed bank",
            campus="Main Campus",
            proposal_status=Proposal.ProposalStatus.APPROVED,
            status=Proposal.OverallStatus.ACTIVE,
            extension_type=Proposal.ExtensionType.COMMUNITY_BASED,
        )
        cls.url = reverse("proposal_implementation_tracker", args=[cls.proposal.pk])

    def post(self, client, **data):
        return client.post(self.url, data, follow=True)

    def test_the_owner_can_submit_documentation_photos(self):
        response = self.post(
            self.owner_client,
            action="upload_documentation",
            documentation_photos=[photo(), photo("second.gif")],
            documentation_caption="Seedling distribution",
        )
        self.assertEqual(response.status_code, 200)
        photos = TerminalReportPhoto.objects.filter(proposal=self.proposal)
        self.assertEqual(photos.count(), 2)
        self.assertEqual(photos.first().caption, "Seedling distribution")
        self.assertEqual(photos.first().uploaded_by, self.owner)

    def test_a_non_image_file_is_rejected(self):
        response = self.post(
            self.owner_client,
            action="upload_documentation",
            documentation_photos=[
                SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf")
            ],
        )
        self.assertContains(response, "is not a JPEG, PNG, WebP, or GIF image")
        self.assertFalse(TerminalReportPhoto.objects.filter(proposal=self.proposal).exists())

    def test_an_oversized_photo_is_rejected(self):
        big = SimpleUploadedFile("huge.jpg", b"x" * (12 * 1024 * 1024 + 1), content_type="image/jpeg")
        response = self.post(
            self.owner_client,
            action="upload_documentation",
            documentation_photos=[big],
        )
        self.assertContains(response, "larger than 12 MB")
        self.assertFalse(TerminalReportPhoto.objects.filter(proposal=self.proposal).exists())

    def test_a_good_photo_survives_a_bad_one_in_the_same_batch(self):
        self.post(
            self.owner_client,
            action="upload_documentation",
            documentation_photos=[
                photo(),
                SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain"),
            ],
        )
        self.assertEqual(TerminalReportPhoto.objects.filter(proposal=self.proposal).count(), 1)

    def test_uploading_nothing_explains_itself(self):
        response = self.post(self.owner_client, action="upload_documentation")
        self.assertContains(response, "Please choose at least one photo")

    def test_a_stranger_cannot_upload(self):
        response = self.post(
            self.stranger_client,
            action="upload_documentation",
            documentation_photos=[photo()],
        )
        # A stranger is turned away at the door — either because they may not
        # view the tracker at all or because they may not upload to it.
        self.assertFalse(TerminalReportPhoto.objects.filter(proposal=self.proposal).exists())
        self.assertIn(response.status_code, (200, 302, 403))

    def test_staff_can_submit_on_the_proponents_behalf(self):
        self.post(
            self.director_client,
            action="upload_documentation",
            documentation_photos=[photo()],
        )
        self.assertTrue(TerminalReportPhoto.objects.filter(proposal=self.proposal).exists())

    def test_the_tracker_shows_submitted_photos(self):
        TerminalReportPhoto.objects.create(proposal=self.proposal, image=photo())
        response = self.owner_client.get(self.url)
        self.assertContains(response, "Documentation Photos")
        self.assertContains(response, "1</span>")  # the count badge

    def test_the_owner_can_remove_a_photo(self):
        record = TerminalReportPhoto.objects.create(proposal=self.proposal, image=photo())
        self.post(self.owner_client, action="remove_documentation", photo_id=record.pk)
        self.assertFalse(TerminalReportPhoto.objects.filter(pk=record.pk).exists())

    def test_a_photo_from_another_proposal_cannot_be_removed(self):
        other = Proposal.objects.create(
            created_by=self.owner,
            title="Another program",
            proposal_status=Proposal.ProposalStatus.APPROVED,
        )
        record = TerminalReportPhoto.objects.create(proposal=other, image=photo())
        self.owner_client.post(
            self.url,
            {"action": "remove_documentation", "photo_id": record.pk},
        )
        self.assertTrue(TerminalReportPhoto.objects.filter(pk=record.pk).exists())
