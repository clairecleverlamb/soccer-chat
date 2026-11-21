from django.db import models


class ChatRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    response_ms = models.FloatField()
    status_code = models.PositiveSmallIntegerField()
    error_type = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status_code} - {self.response_ms:.0f} ms"