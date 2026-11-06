from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.services import KnowledgeLoadError, load_knowledge_file


class Command(BaseCommand):
    help = "Define or update a RAG dataset from a JSONL file, then publish it."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to a JSONL file, one document per line.")
        parser.add_argument(
            "--dataset",
            required=True,
            help="Dataset slug the chatbot will request, such as soccer.",
        )
        parser.add_argument(
            "--name",
            default="",
            help="Display name. Set when creating the dataset, or to rename it.",
        )
        parser.add_argument(
            "--description",
            default="",
            help="What this dataset is for. Applied when you pass this option.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Drop documents whose source_id is not in this file, then publish.",
        )

    def handle(self, *args, **options):
        try:
            release = load_knowledge_file(
                Path(options["file"]),
                options["dataset"],
                replace=options["replace"],
                name=options["name"],
                description=options["description"],
            )
        except KnowledgeLoadError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Published {release.dataset.slug}: "
                f"{release.document_count} documents, {release.chunk_count} chunks."
            )
        )
