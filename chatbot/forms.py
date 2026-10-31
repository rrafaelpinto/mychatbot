from django import forms

from .models import CandidateFact, CandidateProfile
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


class CandidateFactReviewForm(forms.ModelForm):
    """Edit a fact proposal without exposing verification or publication fields."""

    version = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = CandidateFact
        fields = ["fact_type", "content"]
        widgets = {"content": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["version"].initial = self.instance.updated_at.isoformat()

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content or len(content) > 4000:
            raise forms.ValidationError("Enter a fact of at most 4,000 characters.")
        return content
