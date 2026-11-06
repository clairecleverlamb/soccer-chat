"""Root URL configuration for Soccer Chat."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("players/", include("apps.players.urls")),
    path("evaluations/", include("apps.evaluations.urls")),
    path("chat/", include("apps.chat.urls")),
    path("", include("apps.core.urls")),
]
