from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateDocumentStorage(FileSystemStorage):
    """Local private storage with no URL exposure.

    The storage class is intentionally replaceable by private object storage later.
    """

    def __init__(self) -> None:
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)

    def url(self, name: str) -> str:
        raise ValueError("Private candidate documents do not have public URLs.")
