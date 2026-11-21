from datetime import timedelta

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Max, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import render
from django.urls import path
from django.utils import timezone

from .models import ChatRequest


@admin.register(ChatRequest)
class ChatRequestAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "response_ms",
        "status_code",
        "error_type",
    )
    list_filter = ("status_code",)
    date_hierarchy = "created_at"
    list_per_page = 50
    readonly_fields = (
        "created_at",
        "response_ms",
        "status_code",
        "error_type",
    )
    change_list_template = "admin/chat/chatrequest/change_list.html"

    def get_urls(self):
        urls = [
            path(
                "performance/",
                self.admin_site.admin_view(self.performance_view),
                name="chat_performance",
            ),
        ]
        return urls + super().get_urls()

    def performance_view(self, request):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])

        if not self.has_view_permission(request):
            raise PermissionDenied

        since = timezone.now() - timedelta(hours=24)
        requests = ChatRequest.objects.filter(created_at__gte=since)

        stats = requests.aggregate(
            total=Count("pk"),
            successful=Count(
                "pk",
                filter=Q(status_code__gte=200, status_code__lt=400),
            ),
            rejected=Count(
                "pk",
                filter=Q(status_code__gte=400, status_code__lt=500),
            ),
            failed=Count(
                "pk",
                filter=Q(status_code__gte=500),
            ),
            average_ms=Avg("response_ms"),
            maximum_ms=Max("response_ms"),
        )

        stats["failure_rate"] = (
            stats["failed"] / stats["total"] * 100
            if stats["total"]
            else 0
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Chat performance",
            "opts": self.model._meta,
            "stats": stats,
            "since": since,
            "recent_requests": requests.order_by("-created_at")[:20],
        }
        return render(
            request,
            "admin/chat/chatrequest/performance.html",
            context,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False