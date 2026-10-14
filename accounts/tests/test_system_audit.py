"""Cross-cutting regressions discovered in the October UI/flow audit."""
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile, SiteConfiguration
from accounts.tests import factories
from accounts.ui import brand_tokens
from proposals.models import Proposal
from proposals.templatetags.proposal_extras import choice_options


class ThemeTests(TestCase):
    def test_configured_colors_reach_utilities_and_component_styles(self):
        config = SiteConfiguration.get_solo()
        config.primary_color = "#123456"
        config.save()
        response = self.client.get(reverse("login"))
        self.assertContains(response, "--nexus-primary: #123456;")
        self.assertContains(response, "--nexus-primary-rgb: 18 52 86;")
        self.assertContains(response, "css/nexus-utilities.css")
        self.assertNotContains(response, "cdn.tailwindcss.com")

    def test_invalid_stored_color_uses_safe_default(self):
        config = SiteConfiguration(primary_color="invalid")
        self.assertEqual(brand_tokens(config)["primary"]["hex"], "#103b07")

    def test_footer_does_not_invent_missing_contacts_and_has_current_year(self):
        config = SiteConfiguration.get_solo()
        config.contact_email = config.facebook_url = ""
        config.save()
        response = self.client.get("/")
        self.assertNotContains(response, 'href="mailto:')
        self.assertNotContains(response, 'href="https://facebook.com"')
        self.assertContains(response, f"© {timezone.localdate().year}")

    def test_admin_can_clear_contact_fields(self):
        _, client = factories.admin()
        client.post(reverse("admin_site_control"), {"contact_email": "", "facebook_url": ""})
        config = SiteConfiguration.get_solo()
        self.assertEqual(config.contact_email, "")
        self.assertEqual(config.facebook_url, "")

    def test_admin_cannot_save_an_unsafe_contact_url(self):
        _, client = factories.admin()
        original = SiteConfiguration.get_solo().facebook_url
        client.post(reverse("admin_site_control"), {"facebook_url": "javascript:alert(1)"})
        self.assertEqual(SiteConfiguration.get_solo().facebook_url, original)


@override_settings(IDLE_TIMEOUT_SECONDS=120, SESSION_COOKIE_AGE=300)
class SessionPolicyTests(TestCase):
    def setUp(self):
        self.user, self.client = factories.faculty()

    def set_activity(self, seconds_ago):
        session = self.client.session
        session['last_activity'] = (timezone.now() - timedelta(seconds=seconds_ago)).isoformat()
        session.save()

    def test_ui_uses_server_timeout_not_a_separate_constant(self):
        response = self.client.get("/")
        self.assertEqual(response.context['session_config']['timeoutMs'], 120000)
        self.assertContains(response, "js/nexus-session.js")
        self.assertNotContains(response, "30 * 60 * 1000")

    @override_settings(SESSION_COOKIE_AGE=90)
    def test_ui_never_promises_more_than_cookie_lifetime(self):
        response = self.client.get("/")
        self.assertEqual(response.context['session_config']['timeoutMs'], 90000)

    def test_real_activity_renews_a_live_session(self):
        self.set_activity(100)
        response = self.client.post(reverse("session_activity"))
        self.assertEqual(response.status_code, 200)
        last = timezone.datetime.fromisoformat(self.client.session['last_activity'])
        self.assertLess((timezone.now() - last).total_seconds(), 5)

    def test_activity_cannot_resurrect_expired_session(self):
        self.set_activity(121)
        response = self.client.post(reverse("session_activity"))
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_expired_page_request_returns_to_sign_in(self):
        self.set_activity(121)
        self.assertRedirects(self.client.get(reverse('profile_view')), reverse('login'))

    def test_activity_is_post_only_and_requires_authentication(self):
        self.assertEqual(self.client.get(reverse('session_activity')).status_code, 405)
        self.assertEqual(Client().post(reverse('session_activity')).status_code, 401)

    def test_activity_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('session_activity')).status_code, 403)


class AuthRecoveryTests(TestCase):
    def setUp(self):
        self.user, self.client = factories.faculty()

    def test_get_logout_cannot_end_a_session(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_password_change_get_does_not_send_email(self):
        response = self.client.get(reverse('change_password'))
        self.assertContains(response, 'Send reset link')
        self.assertEqual(len(mail.outbox), 0)

    def test_password_change_post_sends_email(self):
        self.assertEqual(self.client.post(reverse('change_password')).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    @patch('accounts.views.auth.PasswordResetForm.save', side_effect=OSError('mail unavailable'))
    def test_password_change_delivery_failure_is_recoverable(self, _save):
        response = self.client.post(reverse('change_password'))
        self.assertContains(response, 'Send reset link')
        self.assertContains(response, 'We could not send the email.')

    def test_duplicate_legacy_emails_do_not_crash_login(self):
        other = factories.make_user('duplicate_email', Profile.ROLE_FACULTY)
        other.email = self.user.email
        other.save()
        response = Client().post(reverse('login'), {'username': self.user.email, 'password': 'wrong'})
        self.assertContains(response, 'Please sign in with your username.')

    def test_failed_login_preserves_identifier_and_posted_destination(self):
        response = Client().post(reverse('login'), {'username': 'retry-user', 'password': 'wrong', 'next': '/profile/'})
        self.assertContains(response, 'value="retry-user"')
        self.assertContains(response, 'name="next" value="/profile/"')
        self.assertContains(response, 'autocomplete="current-password"')


class WizardChoiceTests(TestCase):
    def test_unconfigured_choices_submit_codes_not_python_tuple_strings(self):
        owner, client = factories.faculty()
        proposal = Proposal.objects.create(created_by=owner)
        response = client.get(reverse('proposal_wizard', args=[proposal.pk, 1]))
        self.assertContains(response, 'data-value="COMMUNITY_BASED"')
        self.assertContains(response, 'data-value="PROJECT"')
        self.assertNotContains(response, "(&#x27;COMMUNITY_BASED&#x27;")
        self.assertRegex(response.content.decode(), r'<button[^>]*class="ext-chip')
        self.assertContains(response, 'aria-pressed=')


class AssetAndChoiceContractTests(SimpleTestCase):
    def test_choice_normalization_preserves_admin_labels_and_builtin_codes(self):
        self.assertEqual(choice_options([('A', 'Alpha'), {'value': 'B', 'label': 'Beta'}, 'C']), [
            {'value': 'A', 'label': 'Alpha'}, {'value': 'B', 'label': 'Beta'}, {'value': 'C', 'label': 'C'}])

    def test_runtime_ui_assets_are_present_without_a_network_build(self):
        for name in ['alpine.min.js', 'aos.js', 'aos.css', 'chart.umd.js', 'sortable.min.js', 'fonts.css', 'LICENSES.txt']:
            self.assertTrue((settings.BASE_DIR / 'static/vendor' / name).is_file(), name)

    def test_web_templates_do_not_depend_on_runtime_cdns(self):
        for folder in ['templates', 'accounts/templates', 'details/templates', 'proposals/templates']:
            for path in (settings.BASE_DIR / folder).rglob('*.html'):
                text = path.read_text()
                for host in ['cdn.tailwindcss.com', 'cdn.jsdelivr.net', 'unpkg.com', 'fonts.googleapis.com']:
                    self.assertNotIn(host, text, str(path))


class AdminEditValidationTests(TestCase):
    def setUp(self):
        self.actor, self.client = factories.admin('edit_validator')
        self.target = factories.make_user('edit_subject', campus='Legacy Campus', college='Legacy College', department='Legacy Department')
        self.url = reverse('admin_edit_user', args=[self.target.pk])
        self.data = {
            'username': self.target.username, 'email': self.target.email,
            'full_name': 'Revised Name', 'role': Profile.ROLE_FACULTY,
            'campus': 'Legacy Campus', 'college': 'Legacy College', 'department': 'Legacy Department',
            'is_active': 'on', 'email_verified': 'on',
        }

    def test_unchanged_legacy_scope_survives_a_normal_edit(self):
        self.assertRedirects(self.client.post(self.url, self.data), reverse('admin_dashboard'))
        self.target.profile.refresh_from_db()
        self.assertEqual(self.target.profile.department, 'Legacy Department')
        self.assertEqual(self.target.profile.full_name, 'Revised Name')

    def test_weak_password_is_rejected_without_saving_other_changes(self):
        original_hash = self.target.password
        response = self.client.post(self.url, {**self.data, 'password': 'short'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('password', response.context['form'].errors)
        self.target.refresh_from_db()
        self.assertEqual(self.target.password, original_hash)
        self.assertNotEqual(self.target.profile.full_name, 'Revised Name')

    def test_invalid_email_returns_inline_error_and_preserves_input(self):
        response = self.client.post(self.url, {**self.data, 'email': 'not-an-email'})
        self.assertContains(response, 'value="not-an-email"')
        self.assertIn('email', response.context['form'].errors)

    def test_duplicate_email_is_rejected(self):
        response = self.client.post(self.url, {**self.data, 'email': self.actor.email.upper()})
        self.assertIn('email', response.context['form'].errors)

    def test_invalid_role_is_not_silently_changed_to_faculty(self):
        response = self.client.post(self.url, {**self.data, 'role': 'MADE_UP'})
        self.assertIn('role', response.context['form'].errors)

    def test_changed_parent_cannot_keep_legacy_child(self):
        from accounts.models import Campus
        Campus.objects.create(name='New Campus')
        response = self.client.post(self.url, {**self.data, 'campus': 'New Campus'})
        self.assertIn('college', response.context['form'].errors)

    def test_blank_password_does_not_replace_the_existing_hash(self):
        original_hash = self.target.password
        self.client.post(self.url, {**self.data, 'password': ''})
        self.target.refresh_from_db()
        self.assertEqual(self.target.password, original_hash)
