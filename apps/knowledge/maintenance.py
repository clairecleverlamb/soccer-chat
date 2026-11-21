from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Dataset, Release
from .services import publish_dataset


@transaction.atomic
def clear_dataset(dataset, user=None):
    dataset = Dataset.objects.select_for_update().get(pk=dataset.pk)

    dataset.releases.filter(is_active=True).update(is_active=False)

    return Release.objects.create(
        dataset=dataset,
        published_by=user,
        is_active=True,
        document_count=0,
        chunk_count=0,
    )


@transaction.atomic
def reload_dataset(dataset, user=None):
    dataset = Dataset.objects.select_for_update().get(pk=dataset.pk)

    if not dataset.documents.exists():
        raise ValidationError(
            "This dataset has no source documents to reload."
        )

    return publish_dataset(dataset, user=user)