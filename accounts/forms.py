import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django_ckeditor_5.widgets import CKEditor5Widget

from .campus_data import (
    get_campus_choices,
    get_college_choices,
    get_department_choices,
    is_valid_college_for_campus,
    is_valid_department_for_selection,
)
from .models import Profile
from details.models import DocumentTemplate

User = get_user_model()


def validate_nexus_password_rules(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    return password


class StyledFormMixin:
    text_input_classes = (
        "w-full rounded-xl border border-gray-300 px-4 py-2.5 "
        "focus:ring-2 focus:ring-primary focus:border-primary outline-none"
    )

    select_classes = (
        "w-full rounded-xl border border-gray-300 px-4 py-2.5 "
        "bg-white focus:ring-2 focus:ring-primary focus:border-primary outline-none"
    )

    textarea_classes = (
        "w-full rounded-xl border border-gray-300 px-4 py-2.5 "
        "focus:ring-2 focus:ring-primary focus:border-primary outline-none"
    )

    def apply_styled_widgets(self):
        for name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.Select):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} {self.select_classes}".strip()

            elif isinstance(widget, forms.Textarea):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} {self.textarea_classes}".strip()

            elif isinstance(widget, (forms.TextInput, forms.EmailInput, forms.PasswordInput)):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} {self.text_input_classes}".strip()


class DocumentTemplateForm(StyledFormMixin, forms.ModelForm):
    """Validate the Template Library input before it reaches storage/database."""

    class Meta:
        model = DocumentTemplate
        fields = ["title", "category", "version_label", "description", "file", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styled_widgets()
        self.fields["file"].widget.attrs["class"] = (
            "w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm"
        )
        self.fields["is_active"].widget.attrs["class"] = "sr-only peer"

        # Replacing the file is optional when changing an existing template.
        if self.instance and self.instance.pk:
            self.fields["file"].required = False

    def clean_title(self):
        return (self.cleaned_data.get("title") or "").strip()

    def clean_version_label(self):
        return (self.cleaned_data.get("version_label") or "").strip()

    def clean_description(self):
        return (self.cleaned_data.get("description") or "").strip()


class CampusStructureMixin:
    def setup_dependent_choices(self):
        campus = None
        college = None

        if hasattr(self, "data") and self.data:
            campus = self.data.get("campus") or ""
            college = self.data.get("college") or ""
        elif hasattr(self, "instance") and getattr(self, "instance", None):
            campus = getattr(self.instance, "campus", "") or ""
            college = getattr(self.instance, "college", "") or ""

        self.fields["campus"].choices = [("", "Select Campus")] + get_campus_choices()
        self.fields["college"].choices = [("", "Select College (Optional)")] + get_college_choices(campus)
        self.fields["department"].choices = [("", "Select Department (Optional)")] + get_department_choices(campus, college)

    def clean_campus_college_department(self):
        campus = self.cleaned_data.get("campus", "") or ""
        college = self.cleaned_data.get("college", "") or ""
        department = self.cleaned_data.get("department", "") or ""

        if not campus:
            raise ValidationError({"campus": "Campus is required."})

        if not is_valid_college_for_campus(campus, college):
            raise ValidationError({
                "college": "Selected college does not belong to the selected campus."
            })

        if not is_valid_department_for_selection(campus, college, department):
            raise ValidationError({
                "department": "Selected department does not belong to the selected campus/college."
            })

        return campus, college, department


class RegisterForm(StyledFormMixin, CampusStructureMixin, forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    campus = forms.ChoiceField(required=True)
    college = forms.ChoiceField(required=False)
    department = forms.ChoiceField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        validators=[validate_nexus_password_rules],
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
    )

    class Meta:
        model = User
        fields = [
            "full_name",
            "username",
            "email",
            "campus",
            "college",
            "department",
            "password",
            "confirm_password",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_dependent_choices()
        self.apply_styled_widgets()

        self.fields["full_name"].widget.attrs["placeholder"] = "Enter full name"
        self.fields["username"].widget.attrs["placeholder"] = "Enter username"
        self.fields["email"].widget.attrs["placeholder"] = "Enter email"
        self.fields["password"].widget.attrs["placeholder"] = "Enter password"
        self.fields["confirm_password"].widget.attrs["placeholder"] = "Confirm password"

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        try:
            self.clean_campus_college_department()
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                for field, messages in e.message_dict.items():
                    for message in messages if isinstance(messages, list) else [messages]:
                        self.add_error(field, message)
            else:
                raise

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = (self.cleaned_data.get("email") or "").strip().lower()
        user.first_name = ""
        user.last_name = ""

        if commit:
            user.save()

        return user


class ProfileUpdateForm(StyledFormMixin, CampusStructureMixin, forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=True)
    campus = forms.ChoiceField(required=True)
    college = forms.ChoiceField(required=False)
    department = forms.ChoiceField(required=False)

    class Meta:
        model = Profile
        fields = ["full_name", "campus", "college", "department"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields["full_name"].initial = self.instance.full_name

        self.setup_dependent_choices()
        self.apply_styled_widgets()

        self.fields["full_name"].widget.attrs["placeholder"] = "Enter full name"

    def clean(self):
        cleaned_data = super().clean()

        try:
            self.clean_campus_college_department()
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                for field, messages in e.message_dict.items():
                    for message in messages if isinstance(messages, list) else [messages]:
                        self.add_error(field, message)
            else:
                raise

        return cleaned_data


class AdminCreateUserForm(StyledFormMixin, CampusStructureMixin, forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        validators=[validate_nexus_password_rules],
    )
    full_name = forms.CharField(max_length=150, required=True)
    campus = forms.ChoiceField(required=True)
    college = forms.ChoiceField(required=False)
    department = forms.ChoiceField(required=False)
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_dependent_choices()
        self.apply_styled_widgets()

        self.fields["username"].widget.attrs["placeholder"] = "Enter username"
        self.fields["email"].widget.attrs["placeholder"] = "Enter email"
        self.fields["password"].widget.attrs["placeholder"] = "Enter password"
        self.fields["full_name"].widget.attrs["placeholder"] = "Enter full name"

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_role(self):
        role = (self.cleaned_data.get("role") or "").strip().upper()
        allowed_roles = {choice[0] for choice in Profile.ROLE_CHOICES}
        if role not in allowed_roles:
            raise ValidationError("Invalid role selected.")
        return role

    def clean(self):
        cleaned_data = super().clean()

        try:
            self.clean_campus_college_department()
        except ValidationError as e:
            if hasattr(e, "message_dict"):
                for field, messages in e.message_dict.items():
                    for message in messages if isinstance(messages, list) else [messages]:
                        self.add_error(field, message)
            else:
                raise

        return cleaned_data


class NexusPasswordResetForm(PasswordResetForm, StyledFormMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styled_widgets()
        if "email" in self.fields:
            self.fields["email"].widget.attrs["placeholder"] = "Enter your email"


class NexusSetPasswordForm(SetPasswordForm, StyledFormMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styled_widgets()
        if "new_password1" in self.fields:
            self.fields["new_password1"].widget.attrs["placeholder"] = "Enter new password"
        if "new_password2" in self.fields:
            self.fields["new_password2"].widget.attrs["placeholder"] = "Confirm new password"

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        validate_nexus_password_rules(password)
        return password

# ==============================
# PAGE CONTENT (ADMIN CMS)
# ==============================

class PageSectionForm(forms.ModelForm):
    """
    Form for a public page section (text and data-driven block layouts).

    Exists mainly so the CKEditor 5 widget contributes its JS/CSS via
    ``{{ form.media }}`` in the template.
    """

    # Declared as a plain CharField so admins can type free text such as
    # "Our Impact"; ``clean_anchor`` slugifies it. A SlugField would reject the
    # input before we get a chance to normalise it.
    anchor = forms.CharField(
        required=False,
        max_length=60,
        help_text="Optional #anchor so the section can be linked to directly.",
    )

    # Data-block options. All optional; the template only shows the ones that
    # apply to the chosen layout.
    limit_count = forms.IntegerField(
        required=False,
        min_value=1,
        help_text="How many items to show (Activities / Personnel blocks).",
    )
    target_year = forms.IntegerField(
        required=False,
        min_value=2000,
        max_value=2100,
        help_text="Which year to display (Targets block).",
    )
    cta_label = forms.CharField(required=False, max_length=120)
    cta_url = forms.CharField(
        required=False,
        max_length=300,
        help_text="A site path like /register/ or a full https:// URL.",
    )

    class Meta:
        from details.models import PageSection as _PageSection

        model = _PageSection
        fields = [
            "heading",
            "subheading",
            "body",
            "layout",
            "anchor",
            "image",
            "limit_count",
            "target_year",
            "cta_label",
            "cta_url",
            "is_visible",
        ]
        widgets = {
            "body": CKEditor5Widget(config_name="default"),
        }

    def clean_anchor(self):
        """Accept free text (e.g. "Our Impact") and normalise it to a slug."""
        from django.utils.text import slugify

        return slugify(self.cleaned_data.get("anchor") or "")[:60]

    def clean_cta_url(self):
        """
        Restrict destinations to site paths or http(s) URLs.

        The value lands in an href; anything else (e.g. ``javascript:``) is
        rejected rather than rendered.
        """
        url = (self.cleaned_data.get("cta_url") or "").strip()
        if not url:
            return ""
        if url.startswith("/") or url.startswith("http://") or url.startswith("https://"):
            return url
        raise forms.ValidationError(
            "Use a site path (e.g. /register/) or a full URL starting with https://."
        )

    def clean(self):
        """Require at least a heading or some body content.

        A block bound to a content source is exempt: it renders the builder's
        data, so an empty heading only means "no title above the block" — not
        an empty section. Requiring copy there was how a perfectly populated
        SDG block could still be rejected as blank.
        """
        from django.utils.html import strip_tags

        from details.content_sources import get_content_source

        cleaned = super().clean()
        if get_content_source(cleaned.get("layout")) is not None:
            return cleaned

        heading = (cleaned.get("heading") or "").strip()
        body = strip_tags(cleaned.get("body") or "").strip()
        if not heading and not body:
            raise forms.ValidationError("Add a heading or some content before saving.")
        return cleaned
