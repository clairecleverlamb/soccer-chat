import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from apps.knowledge.models import Dataset, Release, SourceDocument
from apps.knowledge.services import active_chunks, publish_dataset
from apps.knowledge.text import chunk_text


class ChunkTextTests(TestCase):
    def test_short_text_stays_one_chunk(self):
        self.assertEqual(chunk_text("Presses high.", size=100, overlap=10), ["Presses high."])

    def test_long_text_overlaps_and_keeps_the_ending(self):
        text = " ".join(f"word{number}" for number in range(40))
        chunks = chunk_text(text, size=30, overlap=8)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(text.endswith(chunks[-1]))
        self.assertTrue(all(len(chunk) <= 30 for chunk in chunks))

    def test_overlap_must_be_smaller_than_size(self):
        with self.assertRaises(ValueError):
            chunk_text("Presses high.", size=10, overlap=10)


class LoadKnowledgeTests(TestCase):
    def test_import_defines_dataset_and_documents(self):
        path = self._write_jsonl(
            [
                '{"source_id": "player:mbappe:2024-25", "title": "Mbappé", "body": "Attacks the space behind the line."}',
            ]
        )

        call_command(
            "load_knowledge",
            str(path),
            "--dataset",
            "soccer",
            "--name",
            "Soccer knowledge",
        )

        dataset = Dataset.objects.get(slug="soccer")
        self.assertEqual(dataset.name, "Soccer knowledge")
        self.assertEqual(dataset.documents.count(), 1)
        release = dataset.releases.get()
        self.assertTrue(release.is_active)
        self.assertEqual(list(active_chunks("soccer").values_list("text", flat=True)), [
            "Attacks the space behind the line.",
        ])

    def test_same_source_id_updates_the_published_text(self):
        first = self._write_jsonl(
            ['{"source_id": "player:rodri:2024-25", "title": "Rodri", "body": "Old note."}']
        )
        second = self._write_jsonl(
            ['{"source_id": "player:rodri:2024-25", "title": "Rodri", "body": "Receives between the lines."}']
        )
        call_command("load_knowledge", str(first), "--dataset", "soccer")
        call_command("load_knowledge", str(second), "--dataset", "soccer")

        self.assertEqual(SourceDocument.objects.filter(source_id="player:rodri:2024-25").count(), 1)
        self.assertEqual(
            list(active_chunks("soccer").values_list("text", flat=True)),
            ["Receives between the lines."],
        )
        self.assertEqual(Release.objects.filter(dataset__slug="soccer", is_active=True).count(), 1)
        self.assertEqual(Release.objects.filter(dataset__slug="soccer").count(), 2)

    def test_replace_drops_documents_missing_from_the_file(self):
        original = self._write_jsonl(
            [
                '{"source_id": "player:mbappe:2024-25", "title": "Mbappé", "body": "Keep this note."}',
                '{"source_id": "player:rodri:2024-25", "title": "Rodri", "body": "Drop this note."}',
            ]
        )
        updated = self._write_jsonl(
            ['{"source_id": "player:mbappe:2024-25", "title": "Mbappé", "body": "Keep this note."}']
        )
        call_command("load_knowledge", str(original), "--dataset", "soccer")
        call_command("load_knowledge", str(updated), "--dataset", "soccer", "--replace")

        self.assertEqual(
            list(SourceDocument.objects.values_list("source_id", flat=True)),
            ["player:mbappe:2024-25"],
        )
        self.assertEqual(
            list(active_chunks("soccer").values_list("source_id", flat=True)),
            ["player:mbappe:2024-25"],
        )

    def test_invalid_file_leaves_the_active_release_unchanged(self):
        valid = self._write_jsonl(
            ['{"source_id": "guide:pressing-forward", "title": "Pressing", "body": "Pressures start high."}']
        )
        call_command("load_knowledge", str(valid), "--dataset", "soccer")
        active_id = Release.objects.get(is_active=True).pk

        invalid = self._write_jsonl(["{not json"])
        with self.assertRaises(CommandError):
            call_command("load_knowledge", str(invalid), "--dataset", "soccer")

        self.assertEqual(Release.objects.get(is_active=True).pk, active_id)
        self.assertEqual(
            SourceDocument.objects.get().body,
            "Pressures start high.",
        )

    def test_sample_file_publishes_the_soccer_dataset(self):
        from django.conf import settings

        call_command(
            "load_knowledge",
            str(settings.BASE_DIR / "data" / "soccer.jsonl"),
            "--dataset",
            "soccer",
            "--replace",
        )

        self.assertEqual(active_chunks("soccer").count(), 3)
        self.assertTrue(
            active_chunks("soccer")
            .filter(source_id="guide:pressing-forward")
            .exists()
        )

    def _write_jsonl(self, lines: list[str]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "knowledge.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class PublishDraftTests(TestCase):
    def test_editing_a_document_waits_for_publish(self):
        path = self._write("Keep the published note.")
        call_command("load_knowledge", str(path), "--dataset", "soccer")
        document = SourceDocument.objects.get()
        document.body = "A draft note that is not published yet."
        document.save()

        self.assertEqual(
            active_chunks("soccer").get().text,
            "Keep the published note.",
        )
        publish_dataset(document.dataset)
        self.assertEqual(
            active_chunks("soccer").get().text,
            "A draft note that is not published yet.",
        )

    def _write(self, body: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "knowledge.jsonl"
        path.write_text(
            '{"source_id": "player:mbappe:2024-25", "title": "Mbappé", "body": "'
            + body
            + '"}\n',
            encoding="utf-8",
        )
        return path


class KnowledgeAdminTests(TestCase):
    def test_only_staff_can_open_the_dataset_admin(self):
        user = get_user_model().objects.create_user("manager", password="a-long-password")
        self.client.force_login(user)

        response = self.client.get(reverse("admin:knowledge_dataset_changelist"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_publish_action_marks_the_editor(self):
        developer = get_user_model().objects.create_superuser(
            "developer",
            "developer@example.com",
            "a-long-password",
        )
        dataset = Dataset.objects.create(slug="soccer", name="Soccer knowledge")
        SourceDocument.objects.create(
            dataset=dataset,
            source_id="guide:pressing-forward",
            title="Pressing",
            body="Pressures start high.",
        )
        self.client.force_login(developer)

        response = self.client.post(
            reverse("admin:knowledge_dataset_changelist"),
            {"action": "publish_selected", "_selected_action": [str(dataset.pk)]},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published 1 dataset(s).")
        release = dataset.releases.get(is_active=True)
        self.assertEqual(release.published_by, developer)
        self.assertEqual(active_chunks("soccer").get().text, "Pressures start high.")
