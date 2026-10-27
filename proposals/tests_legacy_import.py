"""Legacy imports must join the live workflow, not become disconnected archives."""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.tests import factories
from .models import (
    DocumentationPhoto,
    Proposal,
    ProposalAttachment,
    ProposalPhaseLog,
    ProposalProponent,
)


class LegacyActivityImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.admin_client = factories.admin("import_admin")
        cls.first, cls.first_client = factories.faculty("assigned_one", campus="Main Campus")
        cls.second, cls.second_client = factories.faculty("assigned_two")
        cls.other, cls.other_client = factories.faculty("unassigned")
        cls.director, cls.director_client = factories.director("import_director")
        cls.url = reverse("admin_legacy_proposal_create")

    def data(self, **overrides):
        return {
            "title": "Continuing community training",
            "activity_state": "ONGOING",
            "assigned_proponents": [self.first.pk, self.second.pk],
            "campus": "Main Campus",
            "college": "Computing",
            "department": "Computer Science",
            "extension_type": "COMMUNITY_BASED",
            "scope_type": "ACTIVITY",
            **overrides,
        }

    def create_activity(self, **overrides):
        response = self.admin_client.post(self.url, self.data(**overrides))
        self.assertRedirects(response, reverse("admin_dashboard"), fetch_redirect_response=False)
        return Proposal.objects.get(title="Continuing community training")

    def test_import_sets_completed_earlier_phases_without_requiring_files(self):
        proposal = self.create_activity(proposal_status="DRAFTING")
        self.assertTrue(proposal.is_legacy)
        self.assertEqual(proposal.created_by, self.admin)
        self.assertEqual(proposal.proposal_status, Proposal.ProposalStatus.COMPLETED)
        self.assertEqual(proposal.moa_status, Proposal.MOAStatus.COMPLETED)
        self.assertEqual(proposal.implementation_status, Proposal.ImplementationStatus.IMPLEMENTATION)
        self.assertEqual(proposal.status, Proposal.OverallStatus.ACTIVE)
        self.assertEqual(proposal.proposal_progress, 100)
        self.assertEqual(proposal.moa_progress, 100)
        self.assertLess(proposal.overall_progress, 100)
        self.assertIsNone(proposal.closed_at)
        self.assertFalse(proposal.review_rounds.exists())
        self.assertCountEqual(proposal.proponents.values_list("user_id", flat=True), [self.first.pk, self.second.pk])
        self.assertEqual(proposal.phase_logs.filter(changed_by=self.admin).count(), 2)

    def test_can_import_each_in_progress_implementation_stage(self):
        for stage in ["IMPLEMENTATION", "POST_ACTIVITY_REPORT", "TERMINAL_REPORT", "MONITORING", "REVISION"]:
            with self.subTest(stage=stage):
                response = self.admin_client.post(self.url, self.data(title=stage, implementation_stage=stage))
                self.assertEqual(response.status_code, 302)
                proposal = Proposal.objects.get(title=stage)
                self.assertEqual(proposal.implementation_status, stage)
                self.assertEqual(proposal.status, Proposal.OverallStatus.ACTIVE)

    def test_assigned_accounts_see_activity_and_can_upload_reports(self):
        proposal = self.create_activity()
        tracker = reverse("proposal_implementation_tracker", args=[proposal.pk])
        for client in [self.first_client, self.second_client]:
            dashboard = client.get(reverse("faculty_dashboard"))
            self.assertContains(dashboard, proposal.title)
            self.assertEqual(dashboard.context["implementation_phase_count"], 1)
            self.assertEqual(dashboard.context["completed_phase_count"], 0)
            response = client.get(tracker)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["can_upload"])
            self.assertFalse(response.context["can_manage"])
        response = self.first_client.post(tracker, {
            "action": "upload_progress",
            "report_file": SimpleUploadedFile("progress.pdf", b"interim report"),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.final_documents.get().uploaded_by, self.first)
        # Assigning a proponent doesn't grant the power to advance stages.
        self.first_client.post(tracker, {"action": "advance"})
        proposal.refresh_from_db()
        self.assertEqual(proposal.implementation_status, "IMPLEMENTATION")

    def test_unassigned_account_cannot_see_or_access_import(self):
        proposal = self.create_activity()
        response = self.other_client.get(reverse("faculty_dashboard"))
        self.assertNotContains(response, proposal.title)
        response = self.other_client.get(reverse("proposal_implementation_tracker", args=[proposal.pk]))
        self.assertEqual(response.status_code, 302)

    def test_director_data_counts_import_as_active_implementation(self):
        proposal = self.create_activity()
        response = self.director_client.get(reverse("director_dashboard"))
        self.assertContains(response, proposal.title)
        self.assertEqual(response.context["institution_total"], 1)
        self.assertEqual(response.context["implementation_process_total"], 1)
        self.assertEqual(response.context["institution_completed"], 0)
        self.assertEqual(response.context["campus_stats"][0]["implementation_count"], 1)
        self.assertEqual(response.context["campus_stats"][0]["completed_count"], 0)
        for filters, count in [({"process": "IMPLEMENTATION"}, 1), ({"process": "COMPLETED"}, 0),
                               ({"campus": "Main Campus"}, 1), ({"campus": "Elsewhere"}, 0)]:
            response = self.director_client.get(reverse("director_dashboard"), filters)
            self.assertEqual(response.context["institution_total"], count)

    def test_director_can_continue_normal_workflow(self):
        proposal = self.create_activity()
        response = self.director_client.post(
            reverse("proposal_implementation_tracker", args=[proposal.pk]), {"action": "advance"},
        )
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertNotEqual(proposal.implementation_status, "IMPLEMENTATION")
        self.assertEqual(proposal.status, Proposal.OverallStatus.ACTIVE)

    def test_explicit_completed_import_counts_as_completed(self):
        proposal = self.create_activity(activity_state="COMPLETED")
        self.assertEqual(proposal.status, Proposal.OverallStatus.COMPLETED)
        self.assertEqual(proposal.overall_progress, 100)
        response = self.director_client.get(reverse("director_dashboard"))
        self.assertEqual(response.context["institution_completed"], 1)
        self.assertEqual(response.context["implementation_process_total"], 0)

    def test_form_defaults_and_preserves_submitted_values_on_error(self):
        response = self.admin_client.get(self.url)
        self.assertEqual(response.context["form"]["proposal_status"].value(), "APPROVED")
        self.assertEqual(response.context["form"]["activity_state"].value(), "HISTORICAL")
        response = self.admin_client.post(self.url, self.data(
            title="", beneficiaries_who="Community residents", implementation_stage="MONITORING",
        ))
        self.assertContains(response, "Community residents")
        self.assertEqual(response.context["form"]["implementation_stage"].value(), "MONITORING")
        self.assertEqual(response.context["form"]["activity_state"].value(), "ONGOING")
        self.assertCountEqual(response.context["form"]["assigned_proponents"].value(),
                              [str(self.first.pk), str(self.second.pk)])

    def test_original_historical_contract_still_works(self):
        response = self.admin_client.post(self.url, {"title": "Historical", "proposal_status": "APPROVED"})
        self.assertEqual(response.status_code, 302)
        proposal = Proposal.objects.get()
        self.assertEqual(proposal.proposal_status, "APPROVED")
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")

    def test_documents_do_not_complete_ongoing_activity(self):
        proposal = self.create_activity(
            legacy_proposal_file=SimpleUploadedFile("proposal.pdf", b"proposal"),
            moa_draft_file=SimpleUploadedFile("signed-moa.pdf", b"signed moa"),
            **{"attachments[]": [SimpleUploadedFile("report.pdf", b"report")]},
        )
        self.assertTrue(proposal.legacy_proposal_file)
        self.assertTrue(proposal.moa_draft_file)
        self.assertEqual(proposal.attachments.count(), 1)
        self.assertEqual(proposal.status, Proposal.OverallStatus.ACTIVE)

    def test_validation_errors_create_nothing_and_preserve_values(self):
        inactive = factories.make_user("inactive_account")
        inactive.is_active = False
        inactive.save()
        cases = [
            ({"assigned_proponents": []}, "assigned_proponents"),
            ({"assigned_proponents": [inactive.pk]}, "assigned_proponents"),
            ({"assigned_proponents": [999999]}, "assigned_proponents"),
            ({"activity_state": "BOGUS"}, "activity_state"),
            ({"implementation_stage": "COMPLETED"}, "implementation_stage"),
            ({"implementation_stage": "BOGUS"}, "implementation_stage"),
            ({"beneficiaries_count": -1}, "beneficiaries_count"),
            ({"proposal_status": "BOGUS"}, "proposal_status"),
            ({"title": ""}, "title"),
            ({"certificate_of_completion_file": SimpleUploadedFile("certificate.pdf", b"certificate")}, "certificate_of_completion_file"),
        ]
        for overrides, field in cases:
            with self.subTest(field=field, overrides=overrides):
                response = self.admin_client.post(self.url, self.data(**overrides))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(response.context["form"]["campus"].value(), "Main Campus")
                self.assertFalse(Proposal.objects.exists())
                self.assertFalse(ProposalProponent.objects.exists())
                self.assertFalse(ProposalPhaseLog.objects.exists())

    def test_duplicate_accounts_are_linked_once(self):
        proposal = self.create_activity(assigned_proponents=[self.first.pk, self.first.pk])
        self.assertEqual(proposal.proponents.count(), 1)

    def test_import_carries_the_photo_documentation_into_the_gallery(self):
        """A legacy activity has no terminal report here, so the import files
        the photos the report would have carried (appendix E.13)."""
        gif = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
            b"\x00\x02\x02D\x01\x00;"
        )
        proposal = self.create_activity(
            documentation_photos=[
                SimpleUploadedFile("action.gif", gif, content_type="image/gif"),
                SimpleUploadedFile("crowd.gif", gif, content_type="image/gif"),
            ],
            documentation_caption="Farmers practising compost preparation",
        )

        photos = proposal.documentation_photos.all()
        self.assertEqual(photos.count(), 2)
        self.assertEqual(photos.first().caption, "Farmers practising compost preparation")
        self.assertEqual(photos.first().uploaded_by, self.admin)

        gallery = self.client.get(reverse("gallery_page"))
        self.assertContains(gallery, "Farmers practising compost preparation")
        self.assertContains(gallery, "Legacy upload")

    def test_import_records_what_the_programs_directory_publishes(self):
        proposal = self.create_activity(
            general_objective="Raise household income",
            objectives_specific="Train 30 farmers\nSet up a demo plot",
            student_participants="4",
            faculty_participants="6",
            research_staff_participants="1",
            date_venue="May 7-9, 2025 · Barangay Sabangan",
        )

        self.assertEqual(proposal.general_objective, "Raise household income")
        self.assertEqual(proposal.student_participants, 4)
        self.assertEqual(proposal.faculty_participants, 6)
        self.assertEqual(proposal.research_staff_participants, 1)

        programs = self.client.get(reverse("programs_page"))
        self.assertContains(programs, "Continuing community training")
        self.assertContains(programs, "May 7-9, 2025")

    def test_only_admin_can_import(self):
        for client in [self.first_client, self.director_client]:
            for method in [client.get, client.post]:
                response = method(self.url, self.data())
                self.assertIn(response.status_code, [302, 403])
        self.assertFalse(Proposal.objects.exists())

    def test_database_import_is_atomic(self):
        with patch("proposals.views.legacy.ProposalProponent.objects.create", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                self.admin_client.post(self.url, self.data())
        self.assertFalse(Proposal.objects.exists())
        self.assertFalse(ProposalAttachment.objects.exists())
        self.assertFalse(ProposalPhaseLog.objects.exists())

    def test_proposal_completed_import_defaults_to_moa_not_started(self):
        proposal = self.create_activity(activity_state="MOA_PENDING", implementation_stage="MONITORING")
        self.assertEqual(proposal.proposal_status, "COMPLETED")
        self.assertEqual(proposal.proposal_progress, 100)
        self.assertEqual(proposal.moa_status, "NOT_STARTED")
        self.assertEqual(proposal.moa_progress, 0)
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")
        self.assertEqual(proposal.implementation_progress, 0)
        self.assertEqual(proposal.status, "ACTIVE")
        self.assertIsNone(proposal.closed_at)
        self.assertEqual(proposal.current_phase_label, "MOA")
        self.assertEqual(proposal.current_status_label, "Not Started")
        # Viewing the pending tracker must not silently start either phase.
        response = self.first_client.get(reverse("proposal_moa_tracker", args=[proposal.pk]))
        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual(proposal.moa_status, "NOT_STARTED")
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")

    def test_moa_import_accepts_each_unfinished_moa_stage(self):
        for stage in ["NOT_STARTED", "DRAFT", "LEGAL_REVIEW", "FOR_REVISION",
                      "CERTIFICATION_READY", "AGENDA_AND_PRESENTATION"]:
            with self.subTest(stage=stage):
                response = self.admin_client.post(self.url, self.data(
                    title=stage, activity_state="MOA_PENDING", moa_stage=stage,
                ))
                self.assertEqual(response.status_code, 302)
                proposal = Proposal.objects.get(title=stage)
                self.assertEqual(proposal.moa_status, stage)
                self.assertEqual(proposal.implementation_status, "NOT_STARTED")
                self.assertEqual(proposal.status, "ACTIVE")
                self.assertEqual(proposal.current_phase_label, "MOA")

    def test_pending_moa_appears_for_assigned_accounts_and_director(self):
        proposal = self.create_activity(activity_state="MOA_PENDING")
        for client in [self.first_client, self.second_client]:
            response = client.get(reverse("faculty_dashboard"))
            self.assertContains(response, proposal.title)
            self.assertEqual(response.context["moa_phase_count"], 1)
            self.assertEqual(response.context["proposal_phase_count"], 0)
            self.assertEqual(response.context["implementation_phase_count"], 0)
            self.assertEqual(response.context["completed_phase_count"], 0)
        response = self.director_client.get(reverse("director_dashboard"))
        self.assertEqual(response.context["moa_process_total"], 1)
        self.assertEqual(response.context["implementation_process_total"], 0)
        self.assertEqual(response.context["institution_completed"], 0)
        self.assertEqual(response.context["campus_stats"][0]["moa_count"], 1)
        for phase, count in [("MOA", 1), ("PROPOSAL", 0), ("IMPLEMENTATION", 0), ("COMPLETED", 0)]:
            response = self.director_client.get(reverse("director_dashboard"), {"process": phase})
            self.assertEqual(response.context["institution_total"], count)
        response = self.other_client.get(reverse("proposal_moa_tracker", args=[proposal.pk]))
        self.assertEqual(response.status_code, 302)

    def test_moa_import_can_continue_with_proponent_draft_upload(self):
        proposal = self.create_activity(activity_state="MOA_PENDING")
        response = self.first_client.post(reverse("proposal_moa_draft", args=[proposal.pk]), {
            "action": "upload", "moa_file": SimpleUploadedFile("draft.pdf", b"draft"),
        })
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.moa_status, "DRAFT")
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")
        self.assertEqual(proposal.final_documents.get().uploaded_by, self.first)
        # The ordinary tracker advance remains available to the Director.
        self.director_client.post(reverse("proposal_moa_tracker", args=[proposal.pk]), {"action": "advance"})
        proposal.refresh_from_db()
        self.assertEqual(proposal.moa_status, "LEGAL_REVIEW")
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")

    def test_imported_moa_only_starts_implementation_when_completed(self):
        proposal = self.create_activity(activity_state="MOA_PENDING", moa_stage="AGENDA_AND_PRESENTATION")
        response = self.director_client.post(reverse("proposal_moa_tracker", args=[proposal.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 302)
        proposal.refresh_from_db()
        self.assertEqual(proposal.moa_status, "COMPLETED")
        self.assertEqual(proposal.implementation_status, "IMPLEMENTATION")
        self.assertEqual(proposal.status, "ACTIVE")

    def test_imported_moa_document_does_not_mark_moa_complete(self):
        proposal = self.create_activity(activity_state="MOA_PENDING", moa_stage="LEGAL_REVIEW",
                                        moa_draft_file=SimpleUploadedFile("draft.pdf", b"draft"))
        self.assertTrue(proposal.moa_draft_file)
        self.first_client.get(reverse("proposal_moa_tracker", args=[proposal.pk]))
        proposal.refresh_from_db()
        self.assertEqual(proposal.moa_status, "LEGAL_REVIEW")
        self.assertEqual(proposal.implementation_status, "NOT_STARTED")
        self.assertEqual(proposal.phase_logs.get().to_status, "LEGAL_REVIEW")

    def test_moa_import_validates_assignments_stages_and_documents(self):
        for changes, field in [
            ({"assigned_proponents": []}, "assigned_proponents"),
            ({"moa_stage": "COMPLETED"}, "moa_stage"),
            ({"moa_stage": "NOT_REQUIRED"}, "moa_stage"),
            ({"moa_stage": "INVALID"}, "moa_stage"),
            ({"moa_draft_file": SimpleUploadedFile("draft.pdf", b"draft")}, "moa_draft_file"),
            ({"certificate_of_completion_file": SimpleUploadedFile("certificate.pdf", b"certificate")}, "certificate_of_completion_file"),
        ]:
            with self.subTest(field=field, changes=changes):
                response = self.admin_client.post(self.url, self.data(activity_state="MOA_PENDING", **changes))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(response.context["form"]["activity_state"].value(), "MOA_PENDING")
                self.assertFalse(Proposal.objects.exists())

    def test_import_ux_uses_stage_cards_checkboxes_and_a_review_panel(self):
        response = self.admin_client.get(self.url)
        self.assertContains(response, 'type="radio" name="activity_state"', count=4)
        self.assertContains(response, 'type="checkbox" name="assigned_proponents"')
        self.assertContains(response, 'id="account-search"')
        self.assertContains(response, 'id="live-review"')
        self.assertContains(response, 'id="legacy-import-form" data-native-select')
        self.assertNotContains(response, 'Hold Ctrl or Command')
        self.assertContains(response, 'Choose extension type')
        self.assertContains(response, 'Choose scope')

    def test_import_ux_restores_checked_accounts_and_opens_invalid_optional_details(self):
        response = self.admin_client.post(self.url, self.data(title="", estimated_year=-1))
        self.assertContains(response, 'id="legacy-errors"')
        self.assertContains(response, 'href="#id_title"')
        self.assertContains(response, 'id="id_title_error"')
        self.assertContains(response, '<details class="legacy-optional" open>')
        self.assertContains(response, 'value="ONGOING" id="id_activity_state_2" checked')
        for choice in response.context["form"]["assigned_proponents"]:
            if str(choice.data["value"]) in {str(self.first.pk), str(self.second.pk)}:
                self.assertTrue(choice.data["selected"])
