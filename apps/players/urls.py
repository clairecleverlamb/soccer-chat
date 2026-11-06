from django.urls import path

from .views import PlayerLookupView

app_name = "players"

urlpatterns = [
    path("", PlayerLookupView.as_view(), name="index"),
]
