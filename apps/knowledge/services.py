"""Load a knowledge file and publish the release the chatbot will read."""

import json
import csv
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import transaction
from django.db.models import QuerySet

from .models import Chunk, Dataset, Release, SourceDocument
from .text import chunk_text, document_hash


class KnowledgeLoadError(Exception):
    """The knowledge file could not be published."""


def active_chunks(dataset_slug: str) -> QuerySet[Chunk]:
    """Return the chunks from the dataset's active release, in read order."""
    return Chunk.objects.filter(
        release__dataset__slug=dataset_slug,
        release__is_active=True,
    )


def parse_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into document records, or raise before any write."""
    if not path.is_file():
        raise KnowledgeLoadError(f"File not found: {path}")

    records = []
    first_line_for_source: dict[str, int] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise KnowledgeLoadError(
                f"Line {line_number} is not valid JSON: {exc.msg}."
            ) from exc
        record = _normalize_record(payload, line_number)
        previous = first_line_for_source.get(record["source_id"])
        if previous is not None:
            raise KnowledgeLoadError(
                f"Line {line_number} repeats source_id {record['source_id']!r}, "
                f"first used on line {previous}."
            )
        first_line_for_source[record["source_id"]] = line_number
        records.append(record)
    return records


def load_knowledge_file(
    path: Path,
    dataset_slug: str,
    *,
    replace: bool = False,
    name: str = "",
    description: str = "",
    user=None,
) -> Release:
    """Create or update a dataset from JSONL or CSV and publish that result.

    Parsing happens before the database transaction. An invalid file leaves
    the active release untouched.
    """
    _validate_slug(dataset_slug)
    
    # Route parsing based on file extension
    suffix = path.suffix.lower()
    if suffix == ".csv":
        records = parse_csv(path)
    elif suffix in (".jsonl", ".json"):
        records = parse_jsonl(path)
    else:
        raise KnowledgeLoadError(f"Unsupported file format '{suffix}'. Use .jsonl or .csv.")

    if not records and not replace:
        raise KnowledgeLoadError(
            "The file has no documents. Use --replace to publish an empty dataset."
        )

    with transaction.atomic():
        dataset = _define_dataset(dataset_slug, name=name, description=description)
        seen_ids = []
        for record in records:
            SourceDocument.objects.update_or_create(
                dataset=dataset,
                source_id=record["source_id"],
                defaults={
                    "title": record["title"],
                    "body": record["body"],
                    "metadata": record["metadata"],
                    "content_hash": document_hash(
                        record["title"],
                        record["body"],
                        record["metadata"],
                    ),
                },
            )
            seen_ids.append(record["source_id"])
        if replace:
            stale = dataset.documents.all()
            if seen_ids:
                stale = stale.exclude(source_id__in=seen_ids)
            stale.delete()
        return publish_dataset(dataset, user=user)


def publish_dataset(dataset: Dataset, user=None) -> Release:
    """Copy the current documents into a new active release."""
    size = settings.KNOWLEDGE_CHUNK_SIZE
    overlap = settings.KNOWLEDGE_CHUNK_OVERLAP
    documents = list(dataset.documents.order_by("source_id"))

    with transaction.atomic():
        release = Release.objects.create(
            dataset=dataset,
            published_by=user,
            is_active=False,
            document_count=len(documents),
        )
        chunks = []
        for document in documents:
            metadata = dict(document.metadata or {})
            for ordinal, piece in enumerate(chunk_text(document.body, size, overlap)):
                chunks.append(
                    Chunk(
                        release=release,
                        source_id=document.source_id,
                        title=document.title,
                        ordinal=ordinal,
                        text=piece,
                        metadata=metadata,
                    )
                )
        if chunks:
            Chunk.objects.bulk_create(chunks)
        release.chunk_count = len(chunks)
        Release.objects.filter(dataset=dataset, is_active=True).update(is_active=False)
        release.is_active = True
        release.save(update_fields=["chunk_count", "is_active"])
        return release


def _define_dataset(slug: str, *, name: str, description: str) -> Dataset:
    dataset, created = Dataset.objects.get_or_create(
        slug=slug,
        defaults={"name": name or slug, "description": description},
    )
    if created:
        return dataset
    updates = []
    if name and dataset.name != name:
        dataset.name = name
        updates.append("name")
    if description and dataset.description != description:
        dataset.description = description
        updates.append("description")
    if updates:
        dataset.save(update_fields=updates)
    return dataset


def _validate_slug(slug: str) -> None:
    try:
        validate_slug(slug)
    except ValidationError as exc:
        raise KnowledgeLoadError(
            "Dataset slug may contain letters, numbers, hyphens, and underscores."
        ) from exc


def _normalize_record(payload, line_number: int) -> dict:
    if not isinstance(payload, dict):
        raise KnowledgeLoadError(f"Line {line_number} must be a JSON object.")

    source_id = _required_text(payload, "source_id", line_number, max_length=255)
    title = _required_text(payload, "title", line_number, max_length=300)
    body = _required_text(payload, "body", line_number, max_length=None)
    if "metadata" not in payload or payload["metadata"] is None:
        metadata = {}
    elif isinstance(payload["metadata"], dict):
        metadata = payload["metadata"]
    else:
        raise KnowledgeLoadError(f"Line {line_number} metadata must be a JSON object.")
    return {
        "source_id": source_id,
        "title": title,
        "body": body,
        "metadata": metadata,
    }


def _required_text(payload: dict, field: str, line_number: int, max_length: int | None) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeLoadError(f"Line {line_number} needs a non-empty {field}.")
    text = value.strip()
    if max_length is not None and len(text) > max_length:
        raise KnowledgeLoadError(
            f"Line {line_number} {field} is longer than {max_length} characters."
        )
    return text

def parse_csv(path: Path) -> list[dict]:
    """Read a headerless, positional CSV file into document records, 
    automatically extracting a season prefix from the filename.
    """
    if not path.is_file():
        raise KnowledgeLoadError(f"File not found: {path}")

    # Automatically extract a season/year pattern from the filename (e.g., "2026_2027" or "2026")
    season_match = re.search(r"(\d{4}_\d{4}|\d{4}-\d{4}|\d{4})", path.name)
    season_prefix = season_match.group(1) if season_match else ""

    records = []
    first_line_for_source: dict[str, int] = {}

    try:
        with open(path, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            
            for line_number, row in enumerate(reader, start=1):
                # Skip empty rows
                if not row or not any(row):
                    continue

                # 1. Map positional indices and apply the automatic season prefix to source_id
                raw_id = row[0].strip() if len(row) > 0 else f"row-{line_number}"
                source_id = f"{season_prefix}-{raw_id}" if season_prefix else raw_id
                
                title = row[1].strip() if len(row) > 1 else source_id
                
                # 2. Join all remaining feature columns together into a readable text body
                body_parts = [col.strip() for col in row[2:] if col and col.strip()]
                body = " ".join(body_parts) if body_parts else title

                payload = {
                    "source_id": source_id,
                    "title": title,
                    "body": body,
                    "metadata": {"season": season_prefix} if season_prefix else {},  # Stores season context
                }

                # 3. Run through your existing normalizer and duplicate validator
                record = _normalize_record(payload, line_number)
                previous = first_line_for_source.get(record["source_id"])
                if previous is not None:
                    raise KnowledgeLoadError(
                        f"Line {line_number} repeats source_id {record['source_id']!r}, "
                        f"first used on line {previous}."
                    )
                first_line_for_source[record["source_id"]] = line_number
                records.append(record)
                
    except csv.Error as exc:
        raise KnowledgeLoadError(f"Error parsing CSV file: {exc}") from exc

    return records