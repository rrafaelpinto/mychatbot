from django.contrib.admin.apps import AdminConfig


class SuperuserAdminConfig(AdminConfig):
    default_site = "chatbot.admin_site.SuperuserAdminSite"
