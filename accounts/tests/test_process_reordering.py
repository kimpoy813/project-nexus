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

    def test_process_editor_uses_ajax_and_goey_toast_for_reordering(self):
        response = self.client_admin.get(reverse("process_edit", args=[self.process.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fetch(REORDER_URL")
        self.assertContains(response, "Your previous order was restored")
        self.assertContains(response, "window.goeyToast")
        self.assertNotContains(response, "location.reload")

    def test_ajax_reorder_endpoint_persists_the_submitted_order(self):
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
        editor = self.client_admin.get(
            reverse("process_edit", args=[self.process.pk])
        ).content.decode()
        self.assertLess(editor.index('value="Second"'), editor.index('value="First"'))
