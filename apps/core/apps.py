from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        from django.contrib import admin

        admin.site.site_header = "Soccer Chat admin"
        admin.site.site_title = "Soccer Chat"
        admin.site.index_title = "Players, evaluations, and chat"
