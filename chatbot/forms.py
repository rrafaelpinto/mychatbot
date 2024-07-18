from django import forms
from .models import Candidate

class CandidateRegistrationForm(forms.ModelForm):
    # resume_file = forms.FileField(label='Upload Resume')

    class Meta:
        model = Candidate
        fields = ['name', 'email', 'phone', 'linkedin', 'image', 'resume', 'public_profile']
