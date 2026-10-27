"""Undoing an administrative deletion.

The safety net has to hold in both directions: the row goes away when asked, and
it comes back — with everything a cascade took with it — when the user says so.
These tests use the real views and the real session, because the parts that can
silently break are exactly the ones a unit test of ``deletion.py`` would mock
out: the serializer round-trip, the primary keys, the timestamps and the fact
that a token belongs to one session only.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts import deletion
from accounts.models import Campus, College, Department, Profile, Signatory
from details.models import Activity, ActivityDate, ExtensionProcess, Personnel, ProcessStep

from . import factories


def undo_tokens(html):
    """Every undo token rendered into the page, newest last."""
    import re

    return re.findall(r'data-nx-undo-token="([^"]+)"', html)


class DeleteVerbTests(TestCase):
    """A deletion is a POST; a link must not be able to do it."""

    def setUp(self):
        self.user, self.client = factories.admin("undo_admin")

    def test_the_three_converted_views_refuse_get(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        activity = Activity.objects.create(title="Training", description="…")
        process = ExtensionProcess.objects.create(title="Process")

        for url in (
            reverse("personnel_delete", args=[person.pk]),
            reverse("activity_delete", args=[activity.pk]),
            reverse("process_delete", args=[process.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

        self.assertTrue(Personnel.objects.filter(pk=person.pk).exists())
        self.assertTrue(Activity.objects.filter(pk=activity.pk).exists())
        self.assertTrue(ExtensionProcess.objects.filter(pk=process.pk).exists())

    def test_the_list_no_longer_offers_a_link_to_delete(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        html = self.client.get(reverse("personnel_list")).content.decode()

        self.assertIn(reverse("personnel_delete", args=[person.pk]), html)
        # The URL is in a form's action, never in an href.
        self.assertNotIn(f'href="{reverse("personnel_delete", args=[person.pk])}"', html)


class UndoRestoresTests(TestCase):
    def setUp(self):
        self.user, self.client = factories.admin("undo_admin")

    def test_a_deleted_record_comes_back_with_its_primary_key(self):
        person = Personnel.objects.create(name="Ana", position="Staff", email="ana@example.com")
        pk = person.pk

        response = self.client.post(reverse("personnel_delete", args=[pk]), follow=True)
        self.assertFalse(Personnel.objects.filter(pk=pk).exists())

        token = undo_tokens(response.content.decode())[0]
        self.client.post(reverse("undo_delete", args=[token]), follow=True)

        restored = Personnel.objects.get(pk=pk)
        self.assertEqual(restored.name, "Ana")
        self.assertEqual(restored.email, "ana@example.com")

    def test_undo_restores_the_rows_a_cascade_took(self):
        campus = Campus.objects.create(name="Undo Campus")
        college = College.objects.create(campus=campus, name="College of Undo")
        department = Department.objects.create(campus=campus, college=college, name="Undo Dept")
        ids = (campus.pk, college.pk, department.pk)

        response = self.client.post(reverse("campus_delete", args=[campus.pk]), follow=True)
        self.assertFalse(Campus.objects.filter(pk=campus.pk).exists())
        self.assertFalse(College.objects.filter(pk=college.pk).exists())
        self.assertFalse(Department.objects.filter(pk=department.pk).exists())

        token = undo_tokens(response.content.decode())[0]
        self.client.post(reverse("undo_delete", args=[token]), follow=True)

        self.assertEqual(Department.objects.get(pk=ids[2]).college.pk, ids[1])
        self.assertEqual(College.objects.get(pk=ids[1]).campus.pk, ids[0])

    def test_the_steps_of_a_process_come_back_in_order(self):
        process = ExtensionProcess.objects.create(title="Undo Steps")
        first = ProcessStep.objects.create(process=process, description="First", order=1)
        second = ProcessStep.objects.create(process=process, description="Second", order=2)

        response = self.client.post(reverse("process_delete", args=[process.pk]), follow=True)
        self.assertEqual(ProcessStep.objects.filter(process_id=process.pk).count(), 0)

        token = undo_tokens(response.content.decode())[0]
        self.client.post(reverse("undo_delete", args=[token]), follow=True)

        steps = ProcessStep.objects.filter(process_id=process.pk).order_by("order")
        self.assertEqual([step.pk for step in steps], [first.pk, second.pk])

    def test_an_activitys_dates_come_back(self):
        activity = Activity.objects.create(title="Undo Activity", description="…")
        ActivityDate.objects.create(activity=activity, date=timezone.localdate())

        response = self.client.post(reverse("activity_delete", args=[activity.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]
        self.client.post(reverse("undo_delete", args=[token]), follow=True)

        self.assertEqual(ActivityDate.objects.filter(activity_id=activity.pk).count(), 1)

    def test_created_and_updated_times_are_not_rewritten_by_the_undo(self):
        """A restore is not an edit: the record keeps the dates it had."""
        signatory = Signatory.objects.create(full_name="Dr Undo", position_title="Director")
        Signatory.objects.filter(pk=signatory.pk).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        original = Signatory.objects.get(pk=signatory.pk)

        response = self.client.post(reverse("signatory_delete", args=[signatory.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]
        self.client.post(reverse("undo_delete", args=[token]), follow=True)

        restored = Signatory.objects.get(pk=signatory.pk)
        self.assertEqual(
            restored.created_at.replace(microsecond=0),
            original.created_at.replace(microsecond=0),
        )


class UndoBarTests(TestCase):
    """What the user is told, and where."""

    def setUp(self):
        self.user, self.client = factories.admin("undo_admin")

    def test_the_success_message_says_undo_is_available(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        self.assertContains(response, "You can undo this below.")

    def test_the_bar_names_what_was_deleted(self):
        person = Personnel.objects.create(name="Ana Maria", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)

        html = response.content.decode()
        self.assertIn('data-nx-undo', html)
        self.assertIn("Ana Maria", html)
        self.assertIn("Undo", html)

    def test_the_bar_is_absent_when_nothing_was_deleted(self):
        html = self.client.get(reverse("personnel_list")).content.decode()
        self.assertNotIn("data-nx-undo-token", html)

    def test_dismissing_keeps_the_record_deleted(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]

        self.client.post(reverse("dismiss_undo", args=[token]), follow=True)

        self.assertFalse(Personnel.objects.filter(name="Ana").exists())
        remaining = undo_tokens(self.client.get(reverse("personnel_list")).content.decode())
        self.assertEqual(remaining, [])


class UndoScopeTests(TestCase):
    """Who may undo, for how long, and how many."""

    def setUp(self):
        self.user, self.client = factories.admin("undo_admin")

    def test_another_session_cannot_use_the_token(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]

        _, other = factories.admin("someone_else")
        other.post(reverse("undo_delete", args=[token]), follow=True)

        self.assertFalse(Personnel.objects.filter(name="Ana").exists())

    def test_undo_is_post_only(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]

        self.assertEqual(self.client.get(reverse("undo_delete", args=[token])).status_code, 405)
        self.assertFalse(Personnel.objects.filter(name="Ana").exists())

    def test_undoing_twice_is_harmless(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]

        self.client.post(reverse("undo_delete", args=[token]), follow=True)
        second = self.client.post(reverse("undo_delete", args=[token]), follow=True)

        self.assertContains(second, "can no longer be undone")
        self.assertEqual(Personnel.objects.filter(name="Ana").count(), 1)

    def test_an_expired_entry_is_dropped(self):
        person = Personnel.objects.create(name="Ana", position="Staff")
        response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
        token = undo_tokens(response.content.decode())[0]

        session = self.client.session
        entries = session[deletion.UNDO_SESSION_KEY]
        entries[0]["created"] = timezone.now().timestamp() - deletion.UNDO_LIFETIME - 1
        session[deletion.UNDO_SESSION_KEY] = entries
        session.save()

        self.client.post(reverse("undo_delete", args=[token]), follow=True)
        self.assertFalse(Personnel.objects.filter(name="Ana").exists())

    def test_only_the_newest_five_are_offered(self):
        tokens = []
        for index in range(7):
            person = Personnel.objects.create(name=f"Person {index}", position="Staff")
            response = self.client.post(reverse("personnel_delete", args=[person.pk]), follow=True)
            tokens.extend(undo_tokens(response.content.decode()))

        pending = deletion.pending(self.client.session)
        self.assertEqual(len(pending), deletion.UNDO_LIMIT)
        newest = [item["token"] for item in pending]
        self.assertEqual(newest, tokens[-deletion.UNDO_LIMIT:])

    def test_a_cascade_too_large_to_snapshot_is_not_offered(self):
        person = Personnel.objects.create(name="Ana", position="Staff")

        original = deletion.MAX_ROWS
        deletion.MAX_ROWS = 0
        try:
            response = self.client.post(
                reverse("personnel_delete", args=[person.pk]), follow=True
            )
        finally:
            deletion.MAX_ROWS = original

        # The delete still happens, but nothing pretends it can be undone.
        self.assertFalse(Personnel.objects.filter(pk=person.pk).exists())
        self.assertNotIn("data-nx-undo-token", response.content.decode())


class SnapshotTests(TestCase):
    """The parts of the snapshot that are easy to get wrong."""

    def test_the_cascade_walks_children_and_grandchildren(self):
        campus = Campus.objects.create(name="Cascade Campus")
        college = College.objects.create(campus=campus, name="Cascade College")
        Department.objects.create(campus=campus, college=college, name="Cascade Dept")

        labels = {obj._meta.label_lower for obj in deletion.cascade([campus])}
        self.assertEqual(labels, {"accounts.campus", "accounts.college", "accounts.department"})

    def test_a_profile_is_never_dragged_in_by_a_campus(self):
        """Profiles store campus names, not foreign keys — nothing to cascade."""
        campus = Campus.objects.create(name="Lonely Campus")
        person = Personnel.objects.create(name="Ana", position="Staff")
        self.assertEqual(len(deletion.cascade([campus])), 1)
        self.assertEqual(len(deletion.cascade([person])), 1)

    def test_remembering_nothing_is_safe(self):
        self.assertEqual(deletion.undo_hint(None), "")
        self.assertEqual(deletion.undo_hint("token"), " You can undo this below.")
