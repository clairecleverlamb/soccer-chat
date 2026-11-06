from django.urls import path

from .views import EvaluationView

app_name = "evaluations"

urlpatterns = [
    path("", EvaluationView.as_view(), name="index"),
]
