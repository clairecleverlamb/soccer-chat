from django.conf import settings
from django.db import models

from .text import document_hash


class Dataset(models.Model):
    """Named corpus the RAG chatbot is allowed to read."""

    slug = models.SlugField(
        unique=True,
        help_text="Short name the chatbot will request, such as soccer.",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.name


class SourceDocument(models.Model):
    """Editable source text for one fact in a dataset.

    Saving a document stores the draft. Chatbot answers change only after
    the dataset is published.
    """

    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    source_id = models.CharField(
        max_length=255,
        help_text="Stable id used to update this document on the next import.",
    )
    title = models.CharField(max_length=300)
    body = models.TextField(
        help_text="Editing this text does not change chatbot knowledge until you publish the dataset.",
    )
    metadata = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "source_id"],
                name="unique_source_per_dataset",
            ),
        ]

    def __str__(self):
        return f"{self.source_id}: {self.title}"

    def save(self, *args, **kwargs):
        if self.metadata is None:
            self.metadata = {}
        self.content_hash = document_hash(self.title, self.body, self.metadata)
        super().save(*args, **kwargs)


class Release(models.Model):
    """Published snapshot of a dataset. Only one release per dataset is active."""

    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name="releases",
    )
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="knowledge_releases",
    )
    is_active = models.BooleanField(default=False)
    document_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset"],
                condition=models.Q(is_active=True),
                name="one_active_release_per_dataset",
            ),
        ]

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.dataset.slug} ({state})"


class Chunk(models.Model):
    """One retrieval unit copied from a document at publish time."""

    release = models.ForeignKey(
        Release,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    source_id = models.CharField(max_length=255)
    title = models.CharField(max_length=300)
    ordinal = models.PositiveIntegerField()
    text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["source_id", "ordinal"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "source_id", "ordinal"],
                name="unique_chunk_in_release",
            ),
        ]

    def __str__(self):
        return f"{self.source_id}#{self.ordinal}"
