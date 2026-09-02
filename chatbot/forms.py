from django import forms

from .models import CandidateProfile
from .validators import validate_candidate_document


class CandidateProfileForm(forms.ModelForm):
    linkedin = forms.URLField(required=False, assume_scheme="https")
    document = forms.FileField(
        label="Upload resume",
        help_text="PDF or DOCX, up to 5 MB. Source documents remain private.",
        required=False,
        validators=[validate_candidate_document],
    )

    class Meta:
        model = CandidateProfile
        fields = [
            "name",
            "professional_summary",
            "image",
            "linkedin",
            "show_linkedin",
            "contact_email",
            "show_contact_email",
            "phone",
        ]
        help_texts = {
            "contact_email": "Private unless you explicitly opt in below.",
            "phone": "Always private in Phase 1.",
        }


class ChatQuestionForm(forms.Form):
    question = forms.CharField(max_length=1000, strip=True)
