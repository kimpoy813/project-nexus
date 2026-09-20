"""
The migrations that undo PR #32/#33 must land every database back on PR #28.

``details/0026`` and ``proposals/0049`` are the forward-only half of the
revert. The split's migrations stay in the tree as frozen history because
production may already have run them (``build.sh`` migrates on every deploy),
so the split's schema and its renumbered data have to be rolled forwards to
match the restored models rather than deleted from history - the position
``details/0021`` took for the reverted PR #30.

That is only safe if the rollback is right on every database it can meet, so
these tests run the real migration chain on the test database:

* a fresh install seeds exactly PR #28's 19 steps (``0023`` seeds both flows,
  ``0026`` collapses them again), and
* a database that already carries the split - two flows, renumbered drafts,
  per-step reviewer comments, admin-built step forms - comes back with the
  step table, the research draft's progress, its comments and its step forms
  on the numbers they had before the split, with the columns the restored
  models do not declare dropped.

``details/0027`` (the Utility Model step) now sits on top of the chain, so
"back on PR #28" means PR #28's 19 steps with Utility Model inserted at 7 -
which is exactly ``INITIAL_STEP_LABELS`` - and every step number from the old
Budgetary Requirement onwards one higher than PR #28 had it.

``MigrationExecutor`` moves the schema, so these are ``TransactionTestCase``s
and each one leaves the database back at the leaves for the next test.
"""

import importlib

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from accounts.models import Profile
from accounts.tests import factories
from details.models import DynamicFormTemplate, ProposalWizardStepConfig
from proposals.models import Proposal, ProposalReviewRound, ProposalSectionComment
from proposals.views.constants import INITIAL_STEP_LABELS


# Migrations are importable by name even though the module names start with a
# digit; these are the split's data migrations, replayed to build a database
# that already ran them.
split_wizard = importlib.import_module("details.migrations.0023_split_wizard_into_flows")
agenda_retitles = importlib.import_module("details.migrations.0024_agenda_checklist_retitles")
utility_step = importlib.import_module("details.migrations.0025_split_utility_model_step")

PRE_SPLIT = {
    "details": "0021_undo_wizard_step_parts",
    "proposals": "0046_proponent_sort_order",
}
SPLIT = {
    "details": "0025_split_utility_model_step",
    "proposals": "0048_proposal_technology_title_and_more",
}

# The seeded list: PR #28's 19 steps plus Utility Model at step 7.
PR28_STEPS = [(item["no"], item["title"], item["desc"]) for item in INITIAL_STEP_LABELS]

# PR #28's own list, as a database that pre-dates the Utility Model step held
# it: no step 7 "Utility Model", and everything from Budgetary Requirement on
# one lower.
PRE_UTILITY_STEPS = [
    (no if no < 7 else no - 1, title, desc)
    for no, title, desc in PR28_STEPS
    if title != "Utility Model"
]
PRE_UTILITY_STEPS = [
    (no, title, "SDGs covered and extension thrust" if no == 6 else desc)
    for no, title, desc in PRE_UTILITY_STEPS
]

UTILITY_MODEL_MIGRATION = "0027_utility_model_step"


def utility_shift(step_no):
    """PR #28 step number -> number after the Utility Model insertion."""
    return step_no + 1 if step_no >= 7 else step_no


def migrate(pins=None):
    """Migrate every app to its leaf, except the apps pinned to a migration.

    Returns the historical app registry for the resulting state, which is how
    a test writes rows the way a database at that point in history would have
    them.
    """
    pins = pins or {}
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    targets = []
    for app in sorted(executor.loader.migrated_apps):
        if app in pins:
            targets.append((app, pins[app]))
        else:
            targets.extend(executor.loader.graph.leaf_nodes(app))
    executor.migrate(targets)
    executor.loader.build_graph()
    return executor.loader.project_state(targets).apps


def step_table():
    return [
        (config.step_no, config.title, config.description)
        for config in ProposalWizardStepConfig.objects.order_by("step_no")
    ]


def column_names(table):
    with connection.cursor() as cursor:
        return {column.name for column in connection.introspection.get_table_description(cursor, table)}


class FreshInstallStepTableTests(TestCase):
    def test_migrations_seed_pr_28s_step_list(self):
        """A new database ends on the 20 steps the wizard renders.

        ``0023`` seeds both flows when the step table is empty, ``0026``
        collapses them again and ``0027`` inserts Utility Model at 7, so the
        seed a fresh install gets has to be ``INITIAL_STEP_LABELS`` -
        otherwise the wizard's step pages and the admin's step manager
        disagree about what step 7 is.
        """
        self.assertEqual(step_table(), PR28_STEPS)


class UndoFlowSplitMigrationTests(TransactionTestCase):
    """``0026``/``0049`` against a database that already ran the split."""

    def tearDown(self):
        # A failure part-way through leaves the schema mid-chain; the next
        # test needs the leaves back or every INSERT fails on columns the
        # restored models do not declare.
        migrate()

    def _make_split_database(self):
        """Build a database the way a deployed split left it.

        Called on a database pinned at PR #28 with PR #28's data in it, so
        migrating forward to ``SPLIT`` runs what the deploy ran: ``0023``
        splits the step table into two flows, ``0024`` retitles the
        checklists and ``0025`` moves the utility model into its own step
        (shifting the research steps, draft progress and comments up by one).
        """
        apps = migrate(SPLIT)
        StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
        Comment = apps.get_model("proposals", "ProposalSectionComment")

        # Feedback the office wrote while the split was live, on the two
        # sections it added. A historical model only accepts its own
        # replicas, so these rows are written by id.
        for reviewer_id, rows in (
            (self.agenda_reviewer.pk, ((7, "agenda note"), (8, "utility model note"))),
            (self.funding_reviewer.pk, ((19, "funding note"), (20, "m and e note"))),
        ):
            for step_no, body in rows:
                Comment.objects.create(
                    proposal_id=self.research.pk,
                    review_round_id=self.review_round.pk,
                    reviewer_id=reviewer_id,
                    reviewer_role="EVALUATOR",
                    step_no=step_no,
                    comment=body,
                )
        # A form an admin built for the training flow while it existed.
        apps.get_model("details", "DynamicFormTemplate").objects.create(
            name="Training duration",
            slug="training-duration",
            applies_to="PROPOSAL",
            proposal_wizard_step=8,
            wizard_flow="TRAINING",
        )
        self.assertEqual(StepConfig.objects.filter(flow="TRAINING").count(), 18)
        self.assertEqual(StepConfig.objects.filter(flow="RESEARCH").count(), 21)

    def _create_pr28_data(self, apps):
        """Data as it looked before the split, in PR #28's numbering.

        Written through the historical models for the pinned state, because
        the live ``Proposal`` model now declares the Utility Model columns
        that a database at PR #28 does not have yet.
        """
        HistoricalStepConfig = apps.get_model("details", "ProposalWizardStepConfig")
        HistoricalProposal = apps.get_model("proposals", "Proposal")
        HistoricalRound = apps.get_model("proposals", "ProposalReviewRound")
        HistoricalComment = apps.get_model("proposals", "ProposalSectionComment")
        HistoricalForm = apps.get_model("details", "DynamicFormTemplate")

        # Seed the step list the way PR #28's first wizard visit did in
        # production, so the split's migrations meet a database that already
        # has one. The table is rebuilt rather than topped up: it is empty
        # after a TransactionTestCase flush, but the first test in the class
        # inherits the rows the migrations seeded, and ``step_no`` is unique.
        HistoricalStepConfig.objects.all().delete()
        HistoricalStepConfig.objects.bulk_create(
            [
                HistoricalStepConfig(
                    step_no=no,
                    title=title,
                    description=desc,
                    is_visible=True,
                    is_required=True,
                )
                for no, title, desc in PRE_UTILITY_STEPS
            ]
        )
        self.owner = factories.make_user("mig_owner", Profile.ROLE_FACULTY)
        self.reviewer = factories.make_user("mig_reviewer", Profile.ROLE_EVALUATOR)
        self.agenda_reviewer = factories.make_user("mig_agenda", Profile.ROLE_EVALUATOR)
        self.funding_reviewer = factories.make_user("mig_funding", Profile.ROLE_EVALUATOR)

        self.research = HistoricalProposal.objects.create(
            created_by_id=self.owner.pk,
            extension_type="RESEARCH_FACULTY",
            completed_steps=[1, 2, 3, 6, 7, 12, 18, 19],
            skipped_steps=[8],
            current_step=12,
        )
        self.training = HistoricalProposal.objects.create(
            created_by_id=self.owner.pk,
            extension_type="COMMUNITY_BASED",
            completed_steps=[1, 2, 3, 7, 11],
            skipped_steps=[5],
            current_step=11,
        )
        self.review_round = HistoricalRound.objects.create(proposal_id=self.research.pk, round_no=1)
        self.comments = {}
        for step_no in (6, 7, 8, 9, 18, 19):
            self.comments[step_no] = HistoricalComment.objects.create(
                proposal_id=self.research.pk,
                review_round_id=self.review_round.pk,
                reviewer_id=self.reviewer.pk,
                reviewer_role="EVALUATOR",
                step_no=step_no,
                comment=f"note on step {step_no}",
            )
        self.training_round = HistoricalRound.objects.create(proposal_id=self.training.pk, round_no=1)
        HistoricalComment.objects.create(
            proposal_id=self.training.pk,
            review_round_id=self.training_round.pk,
            reviewer_id=self.reviewer.pk,
            reviewer_role="EVALUATOR",
            step_no=11,
            comment="training note",
        )
        # Admin-built step forms: one the seeder put on a shared step, one an
        # admin attached to a step the split renumbered.
        HistoricalForm.objects.create(
            name="Budget checklist",
            slug="budget-checklist",
            applies_to="PROPOSAL",
            proposal_wizard_step=7,
        )

    def test_an_already_split_database_comes_back_to_pr_28(self):
        # Pin to PR #28 first: that is the numbering the data is written in.
        # (``0027`` on top would otherwise already have the Utility Model
        # step in the table when the split's migrations replay.)
        apps = migrate(PRE_SPLIT)
        self._create_pr28_data(apps)
        before = {
            "completed": [utility_shift(no) for no in self.research.completed_steps],
            "skipped": [utility_shift(no) for no in self.research.skipped_steps],
            "current": utility_shift(self.research.current_step),
            "comments": sorted(utility_shift(no) for no in self.comments),
            "budget_form": utility_shift(7),
        }

        self._make_split_database()
        migrate()

        with self.subTest("step table"):
            self.assertEqual(step_table(), PR28_STEPS)

        with self.subTest("research draft progress"):
            research = Proposal.objects.get(pk=self.research.pk)
            self.assertEqual(list(research.completed_steps), before["completed"])
            self.assertEqual(list(research.skipped_steps), before["skipped"])
            self.assertEqual(research.current_step, before["current"])

        with self.subTest("reviewer comments"):
            steps = sorted(
                ProposalSectionComment.objects.filter(proposal_id=self.research.pk, reviewer=self.reviewer)
                .values_list("step_no", flat=True)
            )
            self.assertEqual(steps, before["comments"])
            for step_no, comment in self.comments.items():
                body = ProposalSectionComment.objects.get(pk=comment.pk).comment
                self.assertEqual(body, f"note on step {step_no}")

        with self.subTest("comments on the steps the split added fold together"):
            # The agenda and utility-model notes both belong to step 6 now,
            # and one reviewer may only hold one comment per step, so they are
            # merged instead of one of them being dropped.
            merged = ProposalSectionComment.objects.get(
                proposal_id=self.research.pk, reviewer=self.agenda_reviewer
            )
            self.assertEqual(merged.step_no, 6)
            self.assertIn("agenda note", merged.comment)
            self.assertIn("utility model note", merged.comment)
            funding = ProposalSectionComment.objects.get(
                proposal_id=self.research.pk, reviewer=self.funding_reviewer
            )
            # Funding Strategy: PR #28's 17, one higher since Utility Model.
            self.assertEqual(funding.step_no, utility_shift(17))
            self.assertIn("funding note", funding.comment)
            self.assertIn("m and e note", funding.comment)

        with self.subTest("no comment is left pointing past the last step"):
            last_step = ProposalWizardStepConfig.objects.order_by("-step_no").first().step_no
            for step_no in ProposalSectionComment.objects.values_list("step_no", flat=True):
                self.assertLessEqual(step_no, last_step)

        with self.subTest("admin-built step forms"):
            budget = DynamicFormTemplate.objects.get(slug="budget-checklist")
            self.assertEqual(budget.proposal_wizard_step, before["budget_form"])
            # A form built for the training flow has no step to sit on; it is
            # detached rather than hung off an unrelated research step.
            training_form = DynamicFormTemplate.objects.get(slug="training-duration")
            self.assertIsNone(training_form.proposal_wizard_step)

        with self.subTest("training draft keeps the steps both forms share"):
            training = Proposal.objects.get(pk=self.training.pk)
            self.assertEqual(list(training.completed_steps), [1, 2, 3])
            self.assertEqual(
                ProposalSectionComment.objects.get(proposal_id=self.training.pk).step_no,
                utility_shift(11),
            )

        with self.subTest("the split's columns are gone"):
            self.assertNotIn("flow", column_names("details_proposalwizardstepconfig"))
            self.assertNotIn("wizard_flow", column_names("details_dynamicformtemplate"))
            proposal_columns = column_names("proposals_proposal")
            for name in ("duration", "funding_source", "monitoring_eval_file"):
                self.assertNotIn(name, proposal_columns)
            # The Utility Model columns are back - added again by
            # ``proposals/0050`` for the new step, after 0049 dropped the
            # split's copies.
            for name in (
                "technology_title",
                "utility_model_registration_number",
                "utility_model_description",
            ):
                self.assertIn(name, proposal_columns)

        with self.subTest("the restored code can still INSERT"):
            # The failure mode 0021 was written for: a NOT NULL column the
            # restored model does not know about breaks the next write.
            ProposalWizardStepConfig.objects.create(step_no=100, title="Admin extra")
            self.assertTrue(ProposalWizardStepConfig.objects.filter(step_no=100).exists())
            Proposal.objects.create(created_by=self.owner, title="New draft")
            self.assertTrue(Proposal.objects.filter(title="New draft").exists())

    def test_steps_added_while_the_split_was_live_keep_their_place(self):
        """Extra steps an admin added are shifted with the list, not lost.

        The split numbered its two flows independently, so once ``flow`` goes
        away a number can be held twice. ``0026`` moves the research extras
        down with the steps that disappeared, folds a step tagged ALL in
        beside them, and pushes a collision to the end instead of aborting the
        deploy on ``step_no``'s unique index.
        """
        apps = migrate(SPLIT)
        StepConfig = apps.get_model("details", "ProposalWizardStepConfig")
        split_wizard.apply(apps, None)
        agenda_retitles.apply(apps, None)
        utility_step.split_utility_model_step(apps, None)
        for flow, step_no, title in (
            ("RESEARCH", 24, "Research extra"),
            ("ALL", 23, "Shared extra"),
            ("TRAINING", 23, "Training extra"),
        ):
            StepConfig.objects.create(flow=flow, step_no=step_no, title=title)

        migrate()

        self.assertEqual(step_table()[:20], PR28_STEPS)
        # 0026 put them on 20 and 21; 0027 moved them up one more.
        self.assertEqual(
            [(no, title) for no, title, _ in step_table()[20:]],
            [(21, "Shared extra"), (22, "Research extra")],
        )
        # The training flow's extra goes with the flow.
        self.assertFalse(
            ProposalWizardStepConfig.objects.filter(title="Training extra").exists()
        )

    def test_a_pre_split_database_survives_the_whole_chain(self):
        """A deploy that never got the split migrates through it and back.

        PR #32 and PR #33 were live for minutes, so a production database may
        well still be at PR #28. ``migrate`` then runs ``0022``-``0025`` and
        ``0026`` in one go, and the data has to come out the other end where
        it went in.
        """
        apps = migrate(PRE_SPLIT)
        self._create_pr28_data(apps)
        before = self.research
        before_comments = sorted(self.comments)

        migrate()

        # Everything comes out where it went in, plus the Utility Model
        # insertion that 0027 applies on top.
        self.assertEqual(step_table(), PR28_STEPS)
        research = Proposal.objects.get(pk=self.research.pk)
        self.assertEqual(
            list(research.completed_steps),
            [utility_shift(no) for no in before.completed_steps],
        )
        self.assertEqual(
            list(research.skipped_steps),
            [utility_shift(no) for no in before.skipped_steps],
        )
        self.assertEqual(research.current_step, utility_shift(before.current_step))
        self.assertEqual(
            sorted(
                ProposalSectionComment.objects.filter(
                    proposal_id=self.research.pk, reviewer=self.reviewer
                ).values_list("step_no", flat=True)
            ),
            [utility_shift(no) for no in before_comments],
        )
        for step_no, comment in self.comments.items():
            self.assertEqual(
                ProposalSectionComment.objects.get(pk=comment.pk).comment,
                f"note on step {step_no}",
            )
        self.assertEqual(
            DynamicFormTemplate.objects.get(slug="budget-checklist").proposal_wizard_step,
            utility_shift(7),
        )
        self.assertNotIn("flow", column_names("details_proposalwizardstepconfig"))
