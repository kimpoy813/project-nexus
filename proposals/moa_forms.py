from django import forms


class MOASubmissionForm(forms.Form):
    partner_agency_name = forms.CharField(
        label="Name of Partner Agency",
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-800 focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-none placeholder-gray-400",
            "placeholder": "e.g. Department of Science and Technology – Region I",
        }),
    )

    partner_address = forms.CharField(
        label="Address",
        widget=forms.Textarea(attrs={
            "class": "w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-800 focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-none placeholder-gray-400 resize-none",
            "rows": 3,
            "placeholder": "Full address of the partner agency",
        }),
    )

    year = forms.IntegerField(
        label="Year",
        min_value=2000,
        max_value=2100,
        widget=forms.NumberInput(attrs={
            "class": "w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-800 focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-none",
            "placeholder": "e.g. 2025",
        }),
    )

    duration = forms.IntegerField(
        label="Duration (years)",
        min_value=1,
        max_value=20,
        initial=3,
        widget=forms.NumberInput(attrs={
            "class": "w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-800 focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-none",
            "placeholder": "e.g. 3",
        }),
    )

    moa_file = forms.FileField(
        label="Upload MOA Draft",
        help_text="Accepted formats: .pdf, .doc, .docx",
        widget=forms.ClearableFileInput(attrs={
            "accept": ".pdf,.doc,.docx",
        }),
    )

    def clean_moa_file(self):
        f = self.cleaned_data.get("moa_file")
        if f:
            allowed = (".pdf", ".doc", ".docx")
            if not f.name.lower().endswith(allowed):
                raise forms.ValidationError("Only .pdf, .doc, and .docx files are accepted.")
            if f.size > 20 * 1024 * 1024:
                raise forms.ValidationError("File must be smaller than 20 MB.")
        return f