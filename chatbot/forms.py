from django import forms
from .models import Candidate

class CandidateRegistrationForm(forms.ModelForm):
    resume_file = forms.FileField(label='Upload Resume', help_text='Only PDF or DOCX files are allowed.', required=False)

    class Meta:
        model = Candidate
        fields = ['name', 'email', 'phone', 'linkedin', 'image', 'resume_file', 'public_profile']

    def clean_resume_file(self):
        resume_file = self.cleaned_data.get('resume_file')
        if resume_file:
            file_ext = resume_file.name.split('.')[-1].lower()
            if file_ext not in ['pdf', 'docx']:
                raise forms.ValidationError('Only PDF or DOCX files are allowed.')
        return resume_file