from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from .maintenance import clear_dataset, reload_dataset
from .models import Chunk, Dataset, Release, SourceDocument
from .services import publish_dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "document_count",
        "active_release_at",
        "knowledge_controls",
    )
    search_fields = ("name", "slug")
    actions = ("publish_selected",)

    def get_urls(self):
        urls = [
            path(
                "<int:dataset_id>/maintenance/<str:operation>/",
                self.admin_site.admin_view(self.maintenance_view),
                name="knowledge_dataset_maintenance",
            ),
        ]
        return urls + super().get_urls()

    @admin.display(description="Documents")
    def document_count(self, dataset):
        return dataset.documents.count()

    @admin.display(description="Active release")
    def active_release_at(self, dataset):
        release = dataset.releases.filter(is_active=True).first()
        if release is None:
            return "Not published"
        return release.published_at

    @admin.display(description="Knowledge base")
    def knowledge_controls(self, dataset):
        clear_url = reverse(
            "admin:knowledge_dataset_maintenance",
            args=[dataset.pk, "clear"],
        )
        reload_url = reverse(
            "admin:knowledge_dataset_maintenance",
            args=[dataset.pk, "reload"],
        )
        return format_html(
            '<a href="{}">Clear</a> | <a href="{}">Reload</a>',
            clear_url,
            reload_url,
        )

    def maintenance_view(self, request, dataset_id, operation):
        if request.method not in ("GET", "POST"):
            return HttpResponseNotAllowed(["GET", "POST"])

        if operation not in ("clear", "reload"):
            raise Http404

        dataset = get_object_or_404(Dataset, pk=dataset_id)

        if not self.has_change_permission(request, dataset):
            raise PermissionDenied

        back_url = reverse("admin:knowledge_dataset_changelist")

        if request.method == "POST":
            try:
                if operation == "clear":
                    clear_dataset(dataset, user=request.user)
                    message = (
                        f"{dataset.name} cleared. "
                        "Source documents were kept for reloading."
                    )
                else:
                    release = reload_dataset(dataset, user=request.user)
                    message = (
                        f"{dataset.name} reloaded: "
                        f"{release.document_count} documents, "
                        f"{release.chunk_count} chunks."
                    )
            except ValidationError as error:
                self.message_user(
                    request,
                    " ".join(error.messages),
                    level=messages.ERROR,
                )
            else:
                self.log_change(
                    request,
                    dataset,
                    f"Knowledge base operation: {operation}",
                )
                self.message_user(
                    request,
                    message,
                    level=messages.SUCCESS,
                )

            return redirect(back_url)

        context = {
            **self.admin_site.each_context(request),
            "title": f"{operation.title()} knowledge base",
            "opts": self.model._meta,
            "dataset": dataset,
            "operation": operation,
            "back_url": back_url,
        }
        return render(
            request,
            "admin/knowledge/dataset/maintenance.html",
            context,
        )

    @admin.action(
        description="Publish selected datasets",
        permissions=["change"],
    )
    def publish_selected(self, request, queryset):
        for dataset in queryset:
            publish_dataset(dataset, user=request.user)
        self.message_user(
            request,
            f"Published {queryset.count()} dataset(s).",
        )


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
