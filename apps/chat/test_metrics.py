from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.http import JsonResponse
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ChatRequest


class ChatMetricsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            username="metrics-admin",
            email="admin@example.com",
            password="test-password",
        )
        cls.staff = User.objects.create_user(
            username="metrics-staff",
            is_staff=True,
        )
        cls.member = User.objects.create_user(
            username="metrics-member",
        )

    def setUp(self):
        self.chat_url = reverse("chat:index")
        self.performance_url = reverse("admin:chat_performance")

    def test_successful_request_records_processing_time(self):
        with patch(
            "apps.chat.views.ChatView.post",
            return_value=JsonResponse({"answer": "Test answer"}),
        ):
            with patch(
                "apps.chat.middleware.perf_counter",
                side_effect=[10.0, 10.25],
            ):
                response = self.client.post(
                    self.chat_url,
                    {"question": "Test question"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatRequest.objects.count(), 1)
        record = ChatRequest.objects.get()
        self.assertAlmostEqual(record.response_ms, 250.0)
        self.assertEqual(record.status_code, 200)
        self.assertEqual(record.error_type, "")

    def test_unhandled_exception_is_recorded(self):
        client = Client(raise_request_exception=False)

        with patch(
            "apps.chat.views.ChatView.post",
            side_effect=RuntimeError("Test failure"),
        ):
            response = client.post(
                self.chat_url,
                {"question": "Test question"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(ChatRequest.objects.count(), 1)
        record = ChatRequest.objects.get()
        self.assertEqual(record.status_code, 500)
        self.assertEqual(record.error_type, "RuntimeError")

    def test_empty_question_is_recorded_as_rejected(self):
        response = self.client.post(
            self.chat_url,
            {"question": "   "},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ChatRequest.objects.get().status_code, 400)

    def test_opening_chat_page_does_not_create_record(self):
        response = self.client.get(self.chat_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatRequest.objects.count(), 0)

    def test_csrf_rejection_is_recorded(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            self.chat_url,
            {"question": "Test question"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ChatRequest.objects.get().status_code, 403)

    def test_metrics_write_failure_does_not_break_chat(self):
        with patch(
            "apps.chat.views.ChatView.post",
            return_value=JsonResponse({"answer": "Test answer"}),
        ):
            with patch(
                "apps.chat.middleware.ChatRequest.objects.create",
                side_effect=DatabaseError("Test database error"),
            ):
                with self.assertLogs(
                    "apps.chat.middleware",
                    level="ERROR",
                ):
                    response = self.client.post(
                        self.chat_url,
                        {"question": "Test question"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Test answer")

    def test_dashboard_statistics_exclude_old_requests(self):
        for status, duration in [(200, 100), (400, 200), (500, 300)]:
            ChatRequest.objects.create(
                status_code=status,
                response_ms=duration,
            )

        old = ChatRequest.objects.create(
            status_code=500,
            response_ms=9000,
        )
        ChatRequest.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        self.client.force_login(self.admin)
        response = self.client.get(self.performance_url)

        self.assertEqual(response.status_code, 200)
        stats = response.context["stats"]
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertAlmostEqual(stats["average_ms"], 200)
        self.assertAlmostEqual(stats["maximum_ms"], 300)
        self.assertAlmostEqual(stats["failure_rate"], 100 / 3)
        self.assertNotIn(
            old.pk,
            [record.pk for record in response.context["recent_requests"]],
        )

    def test_empty_dashboard_displays_without_error(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.performance_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["total"], 0)
        self.assertEqual(response.context["stats"]["failure_rate"], 0)
        self.assertContains(response, "No requests yet")

    def test_staff_without_view_permission_cannot_access_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.performance_url)

        self.assertEqual(response.status_code, 403)

    def test_anonymous_and_regular_users_are_redirected_to_login(self):
        for user in (None, self.member):
            self.client.logout()
            if user is not None:
                self.client.force_login(user)

            with self.subTest(user=user):
                response = self.client.get(self.performance_url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response.url)