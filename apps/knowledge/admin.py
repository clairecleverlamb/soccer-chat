from django.contrib import admin

from .models import Chunk, Dataset, Release, SourceDocument
from .services import publish_dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "document_count", "active_release_at")
    search_fields = ("name", "slug")
    actions = ("publish_selected",)

    @admin.display(description="Documents")
    def document_count(self, dataset: Dataset) -> int:
        return dataset.documents.count()

    @admin.display(description="Active release")
    def active_release_at(self, dataset: Dataset):
        release = dataset.releases.filter(is_active=True).first()
        if release is None:
            return "Not published"
        return release.published_at

    @admin.action(description="Publish selected datasets")
    def publish_selected(self, request, queryset):
        for dataset in queryset:
            publish_dataset(dataset, user=request.user)
        self.message_user(request, f"Published {queryset.count()} dataset(s).")


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("source_id", "title", "dataset", "updated_at")
    list_filter = ("dataset",)
    search_fields = ("source_id", "title", "body")
    readonly_fields = ("content_hash", "updated_at")
    autocomplete_fields = ("dataset",)


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "published_at",
        "is_active",
        "document_count",
        "chunk_count",
        "published_by",
    )
    list_filter = ("dataset", "is_active")
    readonly_fields = (
        "dataset",
        "published_at",
        "published_by",
        "is_active",
        "document_count",
        "chunk_count",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("source_id", "ordinal", "title", "release")
    list_filter = ("release__dataset",)
    search_fields = ("source_id", "title", "text")
    readonly_fields = ("release", "source_id", "title", "ordinal", "text", "metadata")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
