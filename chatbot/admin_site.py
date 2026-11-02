from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError


class SuperuserAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise ValidationError(
                "Only superusers may access administration.", code="invalid_login"
            )


class SuperuserAdminSite(AdminSite):
    login_form = SuperuserAdminAuthenticationForm

    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser
