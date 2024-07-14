from django import forms
from django.contrib.auth.models import User
from django_registration.forms import RegistrationForm


class UserForm(RegistrationForm):

    class Meta(RegistrationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email')
