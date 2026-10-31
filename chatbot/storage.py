from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDocumentStorage(FileSystemStorage):
    """Local private storage with no URL exposure.

    The storage class is intentionally replaceable by private object storage later.
    """

    def __init__(self) -> None:
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)

    def _save(self, name, content):
        if not settings.CANDIDATE_UPLOADS_ENABLED:
            raise PermissionDenied("Candidate uploads are disabled.")
        return super()._save(name, content)

    def url(self, name: str) -> str:
        raise ValueError("Private candidate documents do not have public URLs.")


class DisabledPublicUploadStorage(FileSystemStorage):
    """Prevent media writes before a durable production backend is configured."""

    def _save(self, name, content):
        raise PermissionDenied("Public media uploads are disabled.")

