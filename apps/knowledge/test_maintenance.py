from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from .maintenance import clear_dataset, reload_dataset
from .models import Dataset, SourceDocument
from .services import active_chunks, publish_dataset


class KnowledgeMaintenanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        self.staff = User.objects.create_user(
            username="staff",
            is_staff=True,
        )
        self.member = User.objects.create_user(username="member")

        self.dataset = Dataset.objects.create(
            slug="soccer",
            name="Soccer knowledge",
        )
        self.document = SourceDocument.objects.create(
            dataset=self.dataset,
            source_id="test-player",
            title="Test player",
            body="The player scored twelve goals.",
        )
        self.original_release = publish_dataset(self.dataset)

    def maintenance_url(self, operation):
        return reverse(
            "admin:knowledge_dataset_maintenance",
            args=[self.dataset.pk, operation],
        )

    def test_clear_keeps_source_documents_and_history(self):
        release = clear_dataset(self.dataset, user=self.admin)

        self.assertFalse(active_chunks("soccer").exists())
        self.assertTrue(
            SourceDocument.objects.filter(pk=self.document.pk).exists()
        )
        self.assertTrue(self.original_release.chunks.exists())
        self.assertEqual(release.published_by, self.admin)
        self.assertEqual(release.chunk_count, 0)
        self.assertEqual(
            self.dataset.releases.filter(is_active=True).count(),
            1,
        )

    def test_clear_does_not_affect_other_datasets(self):
        other = Dataset.objects.create(slug="other", name="Other")
        SourceDocument.objects.create(
            dataset=other,
            source_id="other-source",
            title="Other source",
            body="Another dataset's information.",
        )
        publish_dataset(other)

        clear_dataset(self.dataset)

        self.assertTrue(active_chunks("other").exists())

    def test_reload_restores_cleared_knowledge(self):
        clear_dataset(self.dataset)

        release = reload_dataset(self.dataset, user=self.admin)

        self.assertTrue(active_chunks("soccer").exists())
        self.assertEqual(release.document_count, 1)
        self.assertEqual(release.published_by, self.admin)
        self.assertEqual(
            self.dataset.releases.filter(is_active=True).count(),
            1,
        )

    def test_reload_uses_updated_source_documents(self):
        self.document.body = "The player scored twenty goals."
        self.document.save()

        reload_dataset(self.dataset)

        texts = " ".join(
            active_chunks("soccer").values_list("text", flat=True)
        )
        self.assertIn("twenty goals", texts)
        self.assertNotIn("twelve goals", texts)

    def test_reload_rejects_dataset_without_source_documents(self):
        self.dataset.documents.all().delete()
        count_before = self.dataset.releases.count()

        with self.assertRaises(ValidationError):
            reload_dataset(self.dataset)

        self.original_release.refresh_from_db()
        self.assertTrue(self.original_release.is_active)
        self.assertEqual(self.dataset.releases.count(), count_before)

    def test_failed_reload_keeps_previous_release(self):
        count_before = self.dataset.releases.count()

        with patch(
            "apps.knowledge.services.chunk_text",
            side_effect=RuntimeError("Reload failed"),
        ):
            with self.assertRaises(RuntimeError):
                reload_dataset(self.dataset)

        self.original_release.refresh_from_db()
        self.assertTrue(self.original_release.is_active)
        self.assertTrue(active_chunks("soccer").exists())
        self.assertEqual(self.dataset.releases.count(), count_before)

    def test_confirmation_pages_do_not_change_knowledge(self):
        self.client.force_login(self.admin)
        count_before = self.dataset.releases.count()

        for operation in ("clear", "reload"):
            with self.subTest(operation=operation):
                response = self.client.get(
                    self.maintenance_url(operation)
                )
                self.assertEqual(response.status_code, 200)

        self.assertEqual(self.dataset.releases.count(), count_before)
        self.original_release.refresh_from_db()
        self.assertTrue(self.original_release.is_active)

    def test_admin_can_clear_and_reload_from_website(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.maintenance_url("clear"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(active_chunks("soccer").exists())

        response = self.client.post(self.maintenance_url("reload"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(active_chunks("soccer").exists())

    def test_staff_without_permission_cannot_manage_knowledge(self):
        self.client.force_login(self.staff)
        count_before = self.dataset.releases.count()

        for operation in ("clear", "reload"):
            for method in ("get", "post"):
                with self.subTest(operation=operation, method=method):
                    response = getattr(self.client, method)(
                        self.maintenance_url(operation)
                    )
                    self.assertEqual(response.status_code, 403)

        self.assertEqual(self.dataset.releases.count(), count_before)

    def test_anonymous_and_regular_users_cannot_manage_knowledge(self):
        count_before = self.dataset.releases.count()

        for user in (None, self.member):
            self.client.logout()
            if user is not None:
                self.client.force_login(user)

            for operation in ("clear", "reload"):
                for method in ("get", "post"):
                    with self.subTest(
                        user=user,
                        operation=operation,
                        method=method,
                    ):
                        response = getattr(self.client, method)(
                            self.maintenance_url(operation)
                        )
                        self.assertEqual(response.status_code, 302)
                        self.assertIn("/login/", response.url)

        self.assertEqual(self.dataset.releases.count(), count_before)

    def test_clear_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        url = self.maintenance_url("clear")

        response = client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(active_chunks("soccer").exists())

        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        token = client.cookies["csrftoken"].value

        response = client.post(
            url,
            {"csrfmiddlewaretoken": token},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(active_chunks("soccer").exists())