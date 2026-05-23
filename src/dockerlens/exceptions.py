"""Custom exceptions for dockerlens."""

from __future__ import annotations


class DockerLensError(Exception):
    """Base exception for all dockerlens errors."""


class DockerNotAvailable(DockerLensError):
    """Raised when the Docker daemon cannot be reached."""


class ImageNotFound(DockerLensError):
    """Raised when the requested image is not present in the local Docker daemon.

    Attributes:
        image_name: The name/tag of the image that was not found.
    """

    def __init__(self, image_name: str) -> None:
        self.image_name = image_name
        super().__init__(
            f"Image not found locally: {image_name!r}. "
            f"Pull it first with `docker pull {image_name}`."
        )
