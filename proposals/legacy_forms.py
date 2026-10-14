"""Validated admin imports of historical and in-flight extension activities."""
from django import forms
from django.contrib.auth import get_user_model

from .models import Proposal


class ProponentChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, user):
        profile = getattr(user, "profile", None)
        name = getattr(profile, "full_name", "") or user.get_full_name() or user.username
        campus = getattr(profile, "campus", "")
        return f"{name} (@{user.username})" + (f" — {campus}" if campus else "")


class LegacyProposalForm(forms.ModelForm):
    HISTORICAL = "HISTORICAL"
    MOA_PENDING = "MOA_PENDING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"

    activity_state = forms.ChoiceField(
        label="Activity state",
        choices=[
            (HISTORICAL, "Historical proposal"),
            (MOA_PENDING, "Proposal complete · MOA next"),
            (ONGOING, "Implementation in progress"),
            (COMPLETED, "Activity completed"),
        ],
        widget=forms.RadioSelect,
        initial=HISTORICAL,
        required=False,
    )
    moa_stage = forms.ChoiceField(
        label="Current MOA stage",
        choices=[
            (value, label) for value, label in Proposal.MOAStatus.choices
            if value not in {Proposal.MOAStatus.NOT_REQUIRED, Proposal.MOAStatus.COMPLETED}
        ],
        initial=Proposal.MOAStatus.NOT_STARTED,
        required=False,
    )
    implementation_stage = forms.ChoiceField(
        label="Current implementation stage",
        choices=[(value, label) for value, label in Proposal.ImplementationStatus.choices
                 if value not in {Proposal.ImplementationStatus.NOT_STARTED,
                                  Proposal.ImplementationStatus.PREPARATION,
                                  Proposal.ImplementationStatus.COMPLETED}],
        initial=Proposal.ImplementationStatus.IMPLEMENTATION,
        required=False,
    )
    assigned_proponents = ProponentChoices(
        label="Assigned proponent accounts",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Selected accounts will see this activity on their dashboards and can continue the MOA or implementation workflow according to their permissions.",
    )

    class Meta:
        model = Proposal
        fields = [
            "title", "extension_type", "scope_type", "campus", "college", "department",
            "implementing_agency", "beneficiaries_who", "beneficiaries_count",
            "estimated_month", "estimated_year", "extension_venue", "proposal_status",
            "legacy_proposal_file", "moa_draft_file", "certificate_of_completion_file",
        ]
        widgets = {"beneficiaries_who": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True
        self.fields["proposal_status"].required = False
        self.initial["proposal_status"] = Proposal.ProposalStatus.APPROVED
        self.fields["assigned_proponents"].queryset = (
            get_user_model().objects.filter(is_active=True)
            .select_related("profile").order_by("profile__full_name", "username")
        )
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                field.widget.attrs["class"] = "legacy-input"
        for name, prompt in [("extension_type", "Choose extension type"), ("scope_type", "Choose scope")]:
            self.fields[name].choices = [("", prompt)] + [
                (value, label) for value, label in self.fields[name].choices if value
            ]
        self.fields["title"].widget.attrs["placeholder"] = "e.g. Community digital literacy training"
        self.fields["implementing_agency"].widget.attrs["placeholder"] = "Office, college, or partner unit"
        self.fields["extension_venue"].widget.attrs["placeholder"] = "Barangay, venue, or site"
        self.fields["beneficiaries_who"].widget.attrs["placeholder"] = "Describe the community or participants"


    def clean(self):
        data = super().clean()
        state = data.get("activity_state") or self.HISTORICAL
        data["activity_state"] = state
        data["proposal_status"] = data.get("proposal_status") or Proposal.ProposalStatus.APPROVED
        if state in {self.MOA_PENDING, self.ONGOING}:
            if not data.get("assigned_proponents"):
                self.add_error("assigned_proponents", "Assign at least one proponent account for an ongoing activity.")
            if data.get("certificate_of_completion_file"):
                self.add_error("certificate_of_completion_file", "An ongoing activity cannot have a completion certificate. Upload interim reports as supporting documents instead.")

        if state in {self.MOA_PENDING, self.ONGOING, self.COMPLETED}:
            data["proposal_status"] = Proposal.ProposalStatus.COMPLETED
            if state == self.MOA_PENDING:
                self.instance.moa_status = data.get("moa_stage") or Proposal.MOAStatus.NOT_STARTED
                self.instance.implementation_status = Proposal.ImplementationStatus.NOT_STARTED
                # The live tracker treats an uploaded MOA as a draft. Avoid
                # importing a contradictory state that changes on first view.
                if self.instance.moa_status == Proposal.MOAStatus.NOT_STARTED and data.get("moa_draft_file"):
                    self.add_error("moa_draft_file", "Choose Drafting or a later MOA stage when uploading an MOA document. Leave this file empty if MOA has not started.")
            else:
                self.instance.moa_status = Proposal.MOAStatus.COMPLETED
                self.instance.implementation_status = (
                    data.get("implementation_stage") or Proposal.ImplementationStatus.IMPLEMENTATION
                ) if state == self.ONGOING else Proposal.ImplementationStatus.COMPLETED
        else:
            # Preserve the original import contract for historical proposals.
            if data.get("moa_draft_file"):
                self.instance.moa_status = Proposal.MOAStatus.COMPLETED
            if data.get("certificate_of_completion_file"):
                self.instance.implementation_status = Proposal.ImplementationStatus.COMPLETED
        return data
