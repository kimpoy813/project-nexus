import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from details.models import ExtensionProcess, ProcessStep

from . import factories


class ProcessStepReorderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("process_reorder_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)
        self.process = ExtensionProcess.objects.create(title="Review Process")
        self.first = ProcessStep.objects.create(process=self.process, description="First")
        self.second = ProcessStep.objects.create(process=self.process, description="Second")

    def _post_steps(self, rows, url=None, extra=None):
        """Post an outline of ``(ref, step_id, description, parent_ref)``."""
        payload = {
            "step_ref[]": [row[0] for row in rows],
            "step_id[]": [row[1] for row in rows],
            "step_description[]": [row[2] for row in rows],
            "step_parent[]": [row[3] for row in rows],
            "step_editor": "1",
        }
        if extra:
            payload.update(extra)
        return self.client_admin.post(url or reverse("process_edit", args=[self.process.pk]), payload)

    def test_process_editor_loads_the_nested_step_script_and_persist_url(self):
        response = self.client_admin.get(reverse("process_edit", args=[self.process.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/process-steps-editor.js")
        self.assertContains(response, reverse("reorder_process_steps", args=[self.process.pk]))
        # Non-JS fallback: rows already carry their parent reference.
        self.assertContains(response, 'name="step_parent[]"')
        self.assertContains(response, 'data-step-ref="s%d"' % self.first.pk)

    def test_ajax_reorder_endpoint_still_accepts_a_flat_id_list(self):
        response = self.client_admin.post(
            reverse("reorder_process_steps", args=[self.process.pk]),
            data=json.dumps({"step_ids": [self.second.pk, self.first.pk]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(
            list(self.process.steps.values_list("id", flat=True)),
            [self.second.pk, self.first.pk],
        )

    def test_ajax_reorder_endpoint_persists_nesting(self):
        sub = ProcessStep.objects.create(
            process=self.process, description="Sub", parent=self.first
        )

        response = self.client_admin.post(
            reverse("reorder_process_steps", args=[self.process.pk]),
            data=json.dumps(
                {
                    "steps": [
                        {"id": self.first.pk, "parent": ""},
                        {"id": sub.pk, "parent": self.first.pk},
                        {"id": self.second.pk, "parent": ""},
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.json()["ok"], True)
        sub.refresh_from_db()
        self.assertEqual(sub.parent_id, self.first.pk)
        self.assertEqual(sub.order, 2)
        self.second.refresh_from_db()
        self.assertEqual(self.second.order, 3)

    def test_ajax_reorder_ignores_steps_whose_parent_is_not_saved_yet(self):
        """A row added in the browser has no id yet; the form submit owns it."""
        response = self.client_admin.post(
            reverse("reorder_process_steps", args=[self.process.pk]),
            data=json.dumps(
                {"steps": [{"id": self.first.pk, "parent": "99999"}, {"id": self.second.pk, "parent": ""}]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.json(), {"ok": True, "saved": 1})
        self.second.refresh_from_db()
        self.assertEqual(self.second.order, 1)

    def test_ajax_reorder_rejects_a_malformed_payload(self):
        response = self.client_admin.post(
            reverse("reorder_process_steps", args=[self.process.pk]),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["ok"], False)


class ProcessStepNestingTests(TestCase):
    """Sub-steps round-trip through both editors and the public block."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = factories.make_user("process_nesting_admin", Profile.ROLE_ADMIN)

    def setUp(self):
        self.client_admin = factories.make_client(self.admin)

    def _post(self, url, rows, **extra):
        payload = {
            "step_ref[]": [row[0] for row in rows],
            "step_id[]": [row[1] for row in rows],
            "step_description[]": [row[2] for row in rows],
            "step_parent[]": [row[3] for row in rows],
            "step_editor": "1",
        }
        payload.update(extra)
        return self.client_admin.post(url, payload)

    def _outline(self, process):
        return [
            (depth, step.description, step.parent_id)
            for depth, step in process.steps_as_rows()
        ]

    def test_creating_a_process_saves_sub_steps_under_their_parent(self):
        response = self._post(
            reverse("process_create"),
            [
                ("n1", "", "Step 1", ""),
                ("n2", "", "Sub 1.1", "n1"),
                ("n3", "", "Sub 1.1.1", "n2"),
                ("n4", "", "Step 2", ""),
            ],
            title="Nested Process",
        )
        self.assertRedirects(response, reverse("processes_list"))

        process = ExtensionProcess.objects.get(title="Nested Process")
        self.assertEqual(
            self._outline(process),
            [
                (0, "Step 1", None),
                (1, "Sub 1.1", process.steps.get(description="Step 1").pk),
                (2, "Sub 1.1.1", process.steps.get(description="Sub 1.1").pk),
                (0, "Step 2", None),
            ],
        )

    def test_editing_reparents_and_reorders_existing_steps(self):
        process = ExtensionProcess.objects.create(title="Existing")
        one = ProcessStep.objects.create(process=process, description="One")
        two = ProcessStep.objects.create(process=process, description="Two")

        response = self._post(
            reverse("process_edit", args=[process.pk]),
            [
                (f"s{two.pk}", two.pk, "Two", ""),
                (f"s{one.pk}", one.pk, "One", f"s{two.pk}"),
                ("n9", "", "Deep", f"s{one.pk}"),
            ],
            title="Existing",
        )
        self.assertRedirects(response, reverse("processes_list"))

        one.refresh_from_db()
        two.refresh_from_db()
        deep = process.steps.get(description="Deep")
        self.assertEqual(two.parent_id, None)
        self.assertEqual(two.order, 1)
        self.assertEqual(one.parent_id, two.pk)
        self.assertEqual(one.order, 2)
        self.assertEqual(deep.parent_id, one.pk)
        self.assertEqual(deep.order, 3)

    def test_a_new_sub_step_can_hang_off_a_new_parent(self):
        """Neither row exists yet, so the server has to create parents first."""
        process = ExtensionProcess.objects.create(title="Fresh")
        self._post(
            reverse("process_edit", args=[process.pk]),
            [
                ("n1", "", "Parent", ""),
                ("n2", "", "Child", "n1"),
                ("n3", "", "Grandchild", "n2"),
            ],
            title="Fresh",
        )

        parent = process.steps.get(description="Parent")
        child = process.steps.get(description="Child")
        grandchild = process.steps.get(description="Grandchild")
        self.assertEqual(child.parent_id, parent.pk)
        self.assertEqual(grandchild.parent_id, child.pk)
        self.assertEqual(grandchild.depth, 2)

    def test_removing_a_step_deletes_its_sub_steps(self):
        process = ExtensionProcess.objects.create(title="Prune")
        parent = ProcessStep.objects.create(process=process, description="Parent")
        ProcessStep.objects.create(process=process, description="Child", parent=parent)
        keeper = ProcessStep.objects.create(process=process, description="Keeper")

        self._post(
            reverse("process_edit", args=[process.pk]),
            [(f"s{keeper.pk}", keeper.pk, "Keeper", "")],
            title="Prune",
        )

        self.assertEqual(list(process.steps.values_list("description", flat=True)), ["Keeper"])

    def test_a_blank_parent_row_promotes_its_children_instead_of_dropping_them(self):
        process = ExtensionProcess.objects.create(title="Orphan")
        parent = ProcessStep.objects.create(process=process, description="Parent")
        child = ProcessStep.objects.create(process=process, description="Child", parent=parent)

        self._post(
            reverse("process_edit", args=[process.pk]),
            [
                (f"s{parent.pk}", parent.pk, "   ", ""),
                (f"s{child.pk}", child.pk, "Child", f"s{parent.pk}"),
            ],
            title="Orphan",
        )

        child.refresh_from_db()
        self.assertFalse(process.steps.filter(description="Parent").exists())
        self.assertEqual(child.parent_id, None)

    def test_legacy_post_without_references_saves_a_flat_list(self):
        process = ExtensionProcess.objects.create(title="Legacy")
        self.client_admin.post(
            reverse("process_edit", args=[process.pk]),
            {
                "title": "Legacy",
                "step_description[]": ["Alpha", "Beta"],
                "step_id[]": ["", ""],
            },
        )
        self.assertEqual(
            self._outline(process), [(0, "Alpha", None), (0, "Beta", None)]
        )

    def test_inline_home_editor_saves_nested_steps(self):
        response = self._post(
            reverse("home_inline_process_create"),
            [
                ("n1", "", "Inline step", ""),
                ("n2", "", "Inline sub-step", "n1"),
            ],
            title="Inline Process",
        )
        self.assertEqual(response.status_code, 302)

        process = ExtensionProcess.objects.get(title="Inline Process")
        self.assertEqual(self._outline(process)[1][0], 1)

        response = self._post(
            reverse("home_inline_process_update", args=[process.pk]),
            [
                (f"s{step.pk}", step.pk, description, "")
                for step, description in zip(
                    process.steps.all(), ["Renamed", "Promoted"]
                )
            ],
            title="Inline Process",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._outline(process), [(0, "Renamed", None), (0, "Promoted", None)]
        )

    def test_inline_home_editor_can_delete_every_step(self):
        process = ExtensionProcess.objects.create(title="Empty me")
        ProcessStep.objects.create(process=process, description="Gone")

        self.client_admin.post(
            reverse("home_inline_process_update", args=[process.pk]),
            {"title": "Empty me", "step_editor": "1"},
        )

        self.assertEqual(process.steps.count(), 0)

    def test_public_block_renders_sub_steps_as_bullets(self):
        from details.content_sources import get_content_source

        process = ExtensionProcess.objects.create(title="NESTED-BLOCK-MARKER")
        step = ProcessStep.objects.create(process=process, description="NESTED-PARENT-MARKER")
        ProcessStep.objects.create(
            process=process, description="NESTED-CHILD-MARKER", parent=step
        )

        source = get_content_source("PROCESSES")
        html = self.client.get("/").content.decode()
        # The block only renders where a page publishes it, so render it direct.
        from django.template.loader import render_to_string

        rendered = render_to_string(
            source.block_template,
            {"section": None, "data": {"processes": [process]}},
        )
        self.assertIn("NESTED-PARENT-MARKER", rendered)
        self.assertIn("NESTED-CHILD-MARKER", rendered)
        # Top level keeps the numbered circle, sub-steps are bullets.
        self.assertIn("rounded-full bg-primary text-white", rendered)
        self.assertIn('rounded-full bg-primary/50', rendered)
        self.assertNotIn("None", rendered.split("NESTED-PARENT-MARKER")[0][-200:] or "")
        self.assertTrue(html)

    def test_page_containing_the_block_renders_nested_steps(self):
        from details.models import PageSection, SitePage

        process = ExtensionProcess.objects.create(title="PAGE-NEST-MARKER")
        step = ProcessStep.objects.create(process=process, description="PAGE-PARENT-MARKER")
        ProcessStep.objects.create(
            process=process, description="PAGE-CHILD-MARKER", parent=step
        )

        page, _ = SitePage.objects.get_or_create(
            slug="services", defaults={"title": "Services", "is_published": True}
        )
        PageSection.objects.create(
            page=page, layout=PageSection.Layout.PROCESSES, order=1, is_visible=True
        )

        response = self.client.get(reverse("services_home"))
        self.assertContains(response, "PAGE-NEST-MARKER")
        self.assertContains(response, "PAGE-PARENT-MARKER")
        self.assertContains(response, "PAGE-CHILD-MARKER")
