"""Custom exceptions for dockerlens."""

from __future__ import annotations


class DockerLensError(Exception):
    """Base exception for all dockerlens errors."""


class DockerNotAvailable(DockerLensError):
    """Raised when the Docker daemon cannot be reached."""


class ImageNotFound(DockerLensError):
    """Raised when an image is not found locally."""

    def __init__(self, image_name: str) -> None:
        super().__init__(
            f"Image not found locally: {image_name!r}. "
            f"Pull it first with `docker pull {image_name}`."
        )
        self.image_name = image_name


class RemoteRegistryError(DockerLensError):
    """Raised when failing to fetch image data from the remote registry."""

    pass
