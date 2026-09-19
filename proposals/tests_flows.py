"""
The two proposal wizard flows.

Research-based proposals answer the Extension Proposal form (21 steps);
community-based and request-based proposals answer the Extension Training
Design form (19 steps). These walks keep the step sequences, their save
handlers, and the submission gate honest whenever either form changes.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import factories

from .models import Proposal, ProposalProponent
from .views.wizard import (
    get_required_wizard_step_numbers,
    get_visible_wizard_step_numbers,
    proposal_flow,
)


def _workbook():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        "plan.xlsx",
        b"workbook bytes",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class FlowResolutionTests(TestCase):
    """Extension type decides which form's wizard follows Step 1."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("flow_res_owner", Profile.ROLE_FACULTY)

    def _proposal(self, **kwargs):
        return Proposal.objects.create(created_by=self.owner, **kwargs)

    def test_extension_types_map_to_their_flow(self):
        self.assertEqual(proposal_flow(self._proposal(extension_type="RESEARCH_FACULTY")), "RESEARCH")
        self.assertEqual(proposal_flow(self._proposal(extension_type="RESEARCH_STUDENT")), "RESEARCH")
        self.assertEqual(proposal_flow(self._proposal(extension_type="COMMUNITY_BASED")), "TRAINING")
        self.assertEqual(proposal_flow(self._proposal(extension_type="REQUEST_BASED")), "TRAINING")
        self.assertIsNone(proposal_flow(self._proposal()))

    def test_research_flow_lists_every_form_section(self):
        proposal = self._proposal(extension_type="RESEARCH_FACULTY", scope_type="ACTIVITY")
        steps = get_visible_wizard_step_numbers(proposal)
        self.assertEqual(steps, list(range(1, 22)))
        # Extension Proposal form: SDG and Thrust are separate sections, and
        # Monitoring & Evaluation joins before the research-only uploads.
        self.assertEqual(steps[5], 6)
        self.assertEqual(steps[6], 7)

    def test_training_flow_lists_every_form_section(self):
        proposal = self._proposal(extension_type="COMMUNITY_BASED", scope_type="ACTIVITY")
        steps = get_visible_wizard_step_numbers(proposal)
        self.assertEqual(steps, list(range(1, 20)))

    def test_required_steps_follow_the_flow(self):
        research = self._proposal(extension_type="RESEARCH_FACULTY", scope_type="ACTIVITY")
        training = self._proposal(extension_type="COMMUNITY_BASED", scope_type="ACTIVITY")
        self.assertIn(19, get_required_wizard_step_numbers(research))  # M&E upload
        self.assertIn(20, get_required_wizard_step_numbers(research))  # abstract upload
        # The Training Design form has no research-only uploads and no
        # Significance section (its step 13 is Gender Issues instead).
        required_training = get_required_wizard_step_numbers(training)
        self.assertEqual(required_training, list(range(1, 20)))


class ResearchFlowWalkTests(TestCase):
    """A full walk through the Extension Proposal wizard."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("flow_walk_rs", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        ProposalProponent.objects.create(
            proposal=self.proposal, user=self.owner, full_name="Owner", role="Proponent"
        )
        self.client = factories.make_client(self.owner)

    def _post(self, step_no, payload, files=None):
        data = {**payload, "action": "next"}
        data.update(files or {})
        return self.client.post(
            reverse("proposal_wizard", args=[self.proposal.id, step_no]), data
        )

    def test_all_steps_advance_and_persist(self):
        workbook = _workbook()
        walk = [
            (1, {"extension_type": "RESEARCH_FACULTY", "scope_type": "ACTIVITY", "research_title": "Ext study"}),
            (2, {"title": "Tech Transfer Activity"}),
            (3, {}),
            (4, {"implementing_agency": "CTE"}),
            (5, {"beneficiaries_count": "35", "beneficiaries_who": "Farmers"}),
            (6, {"sdg_codes": ["02"], "sdg_explanation_02": "hunger"}),
            (7, {"thrust_names": ["Numeracy and Literacy"], "thrust_explanation_Numeracy and Literacy": "x"}),
            (8, {"budgetary_requirement": "30,000.00"}),
            (9, {"sex_male": "35", "sex_female": "30", "g_lesbian": "35", "g_gay": "30"}),
            (10, {"gender_issue_keys": ["women_role_development"]}),
            (11, {"estimated_month": "October", "estimated_year": "2026", "extension_venue": "ISPSC"}),
            (12, {"rationale_background": "Why"}),
            (13, {"significance": "Big"}),
            (14, {"general_objective": "Obj", "specific_objectives[]": ["a"]}),
            (15, {"methodologies[]": ["Demo"]}),
            (16, {"output_outcomes[]": ["Product"]}),
            (17, {}, {"work_plan_file": workbook, "gantt_chart_file": workbook}),
            (18, {}, {"funding_file": workbook}),
            (19, {}, {"monitoring_eval_file": workbook}),
            (20, {}, {"research_abstract_file": workbook}),
            (21, {}, {"certificate_of_completion_file": workbook}),
        ]
        for step_no, payload, files in [(n, p, None) for n, p in walk[:16]] + walk[16:]:
            response = self._post(step_no, payload, files)
            self.assertEqual(response.status_code, 302, f"step {step_no} failed")
            if step_no < 21:
                self.assertTrue(
                    response["Location"].endswith(f"/edit/step/{step_no + 1}/"),
                    f"step {step_no} did not advance (went to {response['Location']})",
                )

        self.proposal.refresh_from_db()
        self.assertEqual(
            sorted(self.proposal.completed_steps), list(range(1, 22))
        )
        self.assertTrue(self.proposal.monitoring_eval_file)
        # With every required step complete, the submit page opens.
        response = self.client.get(reverse("proposal_submit", args=[self.proposal.id]))
        self.assertEqual(response.status_code, 200)


class TrainingFlowWalkTests(TestCase):
    """A full walk through the Extension Training Design wizard."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = factories.make_user("flow_walk_tr", Profile.ROLE_FACULTY)

    def setUp(self):
        self.proposal = Proposal.objects.create(created_by=self.owner)
        ProposalProponent.objects.create(
            proposal=self.proposal, user=self.owner, full_name="Owner", role="Proponent"
        )
        self.client = factories.make_client(self.owner)

    def _post(self, step_no, payload, files=None):
        data = {**payload, "action": "next"}
        data.update(files or {})
        return self.client.post(
            reverse("proposal_wizard", args=[self.proposal.id, step_no]), data
        )

    def test_all_steps_advance_and_persist(self):
        workbook = _workbook()
        walk = [
            (1, {"extension_type": "COMMUNITY_BASED", "scope_type": "ACTIVITY"}),
            (2, {"title": "Livelihood Training for Fisherfolk"}),
            (3, {}),
            (4, {"implementing_agency": "CTE"}),
            (5, {"beneficiaries_count": "35", "beneficiaries_who": "Barangay Fisherfolk Association"}),
            (6, {"sdg_codes": ["01"], "sdg_explanation_01": "poverty"}),
            (7, {"thrust_names": ["Health and Nutrition"], "thrust_explanation_Health and Nutrition": "x"}),
            (8, {"duration": "October 23, 2025"}),
            (9, {"extension_venue": "ISPSC Main Campus"}),
            (10, {"funding_source": "CTE Extension Fund"}),
            (11, {"budgetary_requirement": "4,500.00"}),
            (12, {"sex_male": "35", "sex_female": "30", "g_lesbian": "35", "g_gay": "30"}),
            (13, {"gender_issue_keys": ["women_role_development"]}),
            (14, {"rationale_background": "Because"}),
            (15, {"general_objective": "Train", "specific_objectives[]": ["Do x"]}),
            (16, {"methodologies[]": ["Lecture"]}),
            (17, {}, {"work_plan_file": workbook}),
            (18, {}, {"funding_file": workbook}),
            (19, {"output_outcomes[]": ["1 Copy of the signed training design"]}),
        ]
        normalized = [
            (item[0], item[1], item[2] if len(item) > 2 else None) for item in walk
        ]
        for step_no, payload, files in normalized:
            response = self._post(step_no, payload, files)
            self.assertEqual(response.status_code, 302, f"step {step_no} failed")
            if step_no < 19:
                self.assertTrue(
                    response["Location"].endswith(f"/edit/step/{step_no + 1}/"),
                    f"step {step_no} did not advance (went to {response['Location']})",
                )

        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.duration, "October 23, 2025")
        self.assertEqual(self.proposal.funding_source, "CTE Extension Fund")
        self.assertEqual(sorted(self.proposal.completed_steps), list(range(1, 20)))
        response = self.client.get(reverse("proposal_submit", args=[self.proposal.id]))
        self.assertEqual(response.status_code, 200)

    def test_the_training_pages_render_the_form_sections(self):
        self._post(1, {"extension_type": "REQUEST_BASED", "scope_type": "ACTIVITY"})
        cases = {
            5: "Coordinating Units",
            8: "Duration",
            9: "Extension Site",
            10: "Funding Source",
            17: "Schedule of Activities",
        }
        for step_no, expected_text in cases.items():
            with self.subTest(step=step_no):
                response = self.client.get(
                    reverse("proposal_wizard", args=[self.proposal.id, step_no])
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_text)

    def test_switching_flow_resets_flow_specific_progress(self):
        walk = [
            (1, {"extension_type": "RESEARCH_FACULTY", "scope_type": "ACTIVITY", "research_title": "T"}),
            (2, {"title": "X"}),
            (3, {}),
            (4, {"implementing_agency": "CTE"}),
            (5, {"beneficiaries_count": "5", "beneficiaries_who": "Farmers"}),
            (8, {"budgetary_requirement": "1,000"}),
            (13, {"significance": "S"}),
        ]
        for step_no, payload, _files in [(n, p, None) for n, p in walk]:
            self._post(step_no, payload)
        self.proposal.refresh_from_db()
        self.assertIn(13, self.proposal.completed_steps)

        # Switching to the Training Design form changes what steps 5+ mean.
        self._post(1, {"extension_type": "COMMUNITY_BASED", "scope_type": "ACTIVITY"})
        self.proposal.refresh_from_db()
        self.assertEqual(sorted(self.proposal.completed_steps), [1, 2, 3, 4])
