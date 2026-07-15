# -----------------------------------------------------------------------
# ADD THIS TO: your moa app's forms.py (e.g. moa/forms.py)
# -----------------------------------------------------------------------

from django import forms

from .models import MOADocument

ALLOWED_EXTENSIONS = [".docx", ".pdf"]


class MOAUploadForm(forms.ModelForm):
    class Meta:
        model = MOADocument
        fields = ["file"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"accept": ".docx,.pdf"}),
        }

    def clean_file(self):
        file = self.cleaned_data["file"]
        name = file.name.lower()
        if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            raise forms.ValidationError("Only .docx or .pdf files are allowed.")
        # 15 MB cap — adjust to your storage constraints
        if file.size > 15 * 1024 * 1024:
            raise forms.ValidationError("File too large. Maximum size is 15MB.")
        return file
