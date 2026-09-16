from django import forms


class MOABaseForm(forms.Form):
    """
    Shared base for the MOA wizard.
    Keeps styling consistent and makes the fields feel guided.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base_text_input = (
            "mt-1 block w-full rounded-2xl border border-slate-300 bg-white "
            "px-4 py-3 text-sm text-slate-900 shadow-sm "
            "focus:border-yellow-600 focus:ring-yellow-600"
        )
        base_textarea = (
            "mt-1 block w-full rounded-2xl border border-slate-300 bg-white "
            "px-4 py-3 text-sm text-slate-900 shadow-sm "
            "focus:border-yellow-600 focus:ring-yellow-600"
        )
        base_date = (
            "mt-1 block w-full rounded-2xl border border-slate-300 bg-white "
            "px-4 py-3 text-sm text-slate-900 shadow-sm "
            "focus:border-yellow-600 focus:ring-yellow-600"
        )
        base_file = (
            "mt-1 block w-full rounded-2xl border border-dashed border-slate-300 bg-white "
            "px-4 py-3 text-sm text-slate-900 shadow-sm "
            "focus:border-yellow-600 focus:ring-yellow-600"
        )

        for name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, (forms.TextInput, forms.EmailInput, forms.URLInput, forms.NumberInput)):
                widget.attrs.setdefault("class", base_text_input)

            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", base_textarea)

            elif isinstance(widget, forms.DateInput):
                widget.attrs.setdefault("class", base_date)
                widget.attrs.setdefault("type", "date")

            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", base_file)

            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault(
                    "class",
                    "mt-1 block w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-yellow-600 focus:ring-yellow-600",
                )

            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300 text-yellow-600 focus:ring-yellow-600")


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MOADraftForm(MOABaseForm):
    moa_title = forms.CharField(
        label="MOA Title",
        max_length=255,
        help_text="Use the official title that will appear on the document.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Memorandum of Agreement between ISPSC and [Partner] for [Project Name]",
        }),
    )
    moa_reference_no = forms.CharField(
        label="Reference Number",
        max_length=100,
        required=False,
        help_text="Optional. Use this only if your office already assigned one.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. ISPSC-MOA-2026-001",
        }),
    )
    moa_start_date = forms.DateField(
        label="Effectivity Start Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    moa_end_date = forms.DateField(
        label="Effectivity End Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    purpose = forms.CharField(
        label="Purpose of Agreement",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "e.g. To establish a collaboration for joint research, training, and resource sharing to support community development projects.",
        }),
        help_text="Write 1–3 clear sentences about why the MOA is needed.",
    )
    background = forms.CharField(
        label="Background / Rationale",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "Explain the partnership need, program basis, or institutional context.",
        }),
        required=False,
        help_text="Explain the context, partnership need, or program basis.",
    )


class MOAPartiesForm(MOABaseForm):
    party_one_name = forms.CharField(
        label="Party 1 Name",
        help_text="Write the official name of the first party.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Ilocos Sur Polytechnic State College",
        }),
    )
    party_one_representative = forms.CharField(
        label="Party 1 Representative",
        required=False,
        help_text="Person authorized to sign or represent Party 1.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Dr. Maria Santos, College President",
        }),
    )
    party_two_name = forms.CharField(
        label="Party 2 Name",
        help_text="Write the official name of the second party.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. [Partner Organization/Agency Name]",
        }),
    )
    party_two_representative = forms.CharField(
        label="Party 2 Representative",
        required=False,
        help_text="Person authorized to sign or represent Party 2.",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Engr. Juan Dela Cruz, Project Head",
        }),
    )
    signatories_notes = forms.CharField(
        label="Signatory Notes",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "List signatories, titles, and any witness requirements.",
        }),
        required=False,
        help_text="List the signatories, titles, and any required witness names.",
    )


class MOATermsForm(MOABaseForm):
    obligations = forms.CharField(
        label="Roles and Responsibilities",
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Describe what each party will do and what they commit to deliver.",
        }),
        help_text="List each party’s responsibilities using bullets or short paragraphs.",
    )
    deliverables = forms.CharField(
        label="Expected Deliverables",
        widget=forms.Textarea(attrs={
            "rows": 5,
            "placeholder": "e.g. Quarterly progress report, training certificates, equipment handover documents.",
        }),
        required=False,
        help_text="Include outputs such as reports, deliverables, or documentary requirements.",
    )
    confidentiality = forms.CharField(
        label="Confidentiality / Data Sharing Terms",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "State whether information is confidential, how data is shared, and any restrictions.",
        }),
        required=False,
        help_text="Add privacy, confidentiality, or data use rules if needed.",
    )


class MOAAttachmentsForm(MOABaseForm):
    moa_file = forms.FileField(
        label="Upload Draft MOA",
        required=False,
        help_text="Upload the draft file if you already have one.",
    )
    supporting_docs = forms.FileField(
        label="Supporting Documents",
        required=False,
        widget=MultiFileInput(attrs={"multiple": True}),
        help_text="Upload related files such as letters, endorsements, or annexes.",
    )