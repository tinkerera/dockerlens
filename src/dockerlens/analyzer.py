"""Core image analyzer — the main entry point for dockerlens.

Provides :class:`ImageAnalyzer`, which wraps Docker SDK calls and exposes
layer inspection, audit scanning, filesystem diffing, and rich terminal output.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import docker
import docker.errors

from dockerlens.audit import AuditEngine
from dockerlens.diff import DiffEngine
from dockerlens.exceptions import DockerNotAvailable, ImageNotFound, RemoteRegistryError
from dockerlens.models import AuditResult, DiffEntry, ImageReport, Layer
from dockerlens.remote import fetch_remote_image_data
from dockerlens.renderer import render_audit, render_diff, render_layers


class ImageAnalyzer:
    """Analyze a Docker image for layer structure, security issues, and diffs.

    Args:
        image: The image name/tag to analyze, e.g. ``"nginx:latest"``
            or ``"myapp:v1.2"``.
        docker_client: Optional pre-configured :class:`docker.DockerClient`
            instance. If ``None``, a default client is created from the
            environment.

    Raises:
        DockerNotAvailable: If the Docker daemon cannot be reached.
        ImageNotFound: If the specified image is not present locally.
    """

    def __init__(
        self,
        image: str,
        docker_client: docker.DockerClient | None = None,
        remote: bool = False,
    ) -> None:
        self._image_name = image
        self._remote = remote

        if remote:
            self._attrs, self._history = fetch_remote_image_data(image)
        else:
            # Connect to the Docker daemon
            if docker_client is not None:
                self._client = docker_client
            else:
                try:
                    self._client = docker.from_env()
                except docker.errors.DockerException as exc:
                    raise DockerNotAvailable(
                        "Could not connect to the Docker daemon. Is Docker running?"
                    ) from exc

            # Fetch the image object
            try:
                self._image = self._client.images.get(image)
            except docker.errors.ImageNotFound as exc:
                raise ImageNotFound(image) from exc
            except docker.errors.DockerException as exc:
                raise DockerNotAvailable(
                    f"Lost connection to the Docker daemon while fetching image {image!r}."
                ) from exc

            # Cache inspect data and history
            self._attrs: dict = self._image.attrs  # type: ignore[type-arg]
            self._history: list[dict] = self._image.history()  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def layers(self) -> list[Layer]:
        """Return an ordered list of image layers from base to top.

        Each layer contains its digest, uncompressed size, the command
        that created it, and its creation timestamp.

        Returns:
            A list of :class:`Layer` dataclass instances, ordered from
            bottom (index 0) to top.
        """
        rootfs_layers: list[str] = self._attrs.get("RootFS", {}).get("Layers", [])

        # Docker history is returned newest-first; reverse it so index 0
        # corresponds to the base layer.
        history_entries = list(reversed(self._history))

        layers: list[Layer] = []
        digest_idx = 0

        for i, entry in enumerate(history_entries):
            # History entries with empty_layer=True (e.g. ENV, LABEL, CMD)
            # do not produce a filesystem layer and have no corresponding
            # digest in RootFS.Layers.
            created_by: str = entry.get("CreatedBy", "")
            size: int = entry.get("Size", 0)

            # Determine the digest: only real (non-empty) layers have one
            is_empty = size == 0 and entry.get("Id", "<missing>") == "<missing>"
            if not is_empty and digest_idx < len(rootfs_layers):
                digest = rootfs_layers[digest_idx]
                digest_idx += 1
            else:
                digest = "<none>"

            # Parse timestamp — Docker gives us a Unix epoch int or an
            # ISO-8601 string depending on the SDK version.
            raw_created = entry.get("Created", 0)
            if isinstance(raw_created, (int, float)):
                created_at = datetime.fromtimestamp(
                    raw_created, tz=timezone.utc
                ).isoformat()
            else:
                created_at = str(raw_created)

            layers.append(
                Layer(
                    index=i,
                    digest=digest,
                    size_bytes=size,
                    command=created_by,
                    created_at=created_at,
                )
            )

        return layers

    def audit(self) -> list[AuditResult]:
        """Run all built-in audit rules against the image and return findings.

        Checks performed include:

        - Whether the image runs as root (missing ``USER`` instruction)
        - Whether apt/apk package manager caches were cleared
        - Whether the image uses a ``latest`` tag (non-reproducible builds)
        - Whether any layer contains patterns that suggest hardcoded secrets
        - Whether there are unnecessary layers that could be squashed
        - Whether ``ADD`` was used instead of ``COPY``
        - Whether any single layer is unusually large

        Returns:
            A list of :class:`AuditResult` instances. An empty list means
            no issues were found.
        """
        engine = AuditEngine(self._attrs, self._history)
        return engine.run_all()

    def diff(
        self,
        other: str,
        include_paths: Sequence[str] | None = None,
        exclude_paths: Sequence[str] | None = None,
    ) -> list[DiffEntry]:
        """Compare this image's filesystem against another image.

        Exports both images as tarballs, extracts the file trees, and
        returns a list of filesystem differences.

        Args:
            other: The image name/tag to compare against.
            include_paths: If provided, only report changes under these
                path prefixes.
            exclude_paths: If provided, exclude changes under these
                path prefixes.

        Returns:
            A list of :class:`DiffEntry` instances describing added,
            removed, and modified files.

        Raises:
            ImageNotFound: If the *other* image is not present locally.
            DockerLensError: If called on a remotely fetched image.
        """
        if self._remote:
            raise RemoteRegistryError("diff command requires local images. Remote scanning is only for metadata/audit.")
            
        try:
            other_image = self._client.images.get(other)
        except docker.errors.ImageNotFound as exc:
            raise ImageNotFound(other) from exc

        engine = DiffEngine(self._image, other_image)
        return engine.compare(
            include_paths=include_paths,
            exclude_paths=exclude_paths,
        )

    def report(self) -> ImageReport:
        """Generate a full report combining layers and audit results.

        Returns:
            An :class:`ImageReport` dataclass that can be serialized to JSON.
        """
        return ImageReport(
            image_name=self._image_name,
            image_id=self._attrs.get("Id", ""),
            total_size_bytes=self._attrs.get("Size", 0),
            layers=self.layers(),
            audit_results=self.audit(),
        )

    # ------------------------------------------------------------------
    # Pretty-printing helpers
    # ------------------------------------------------------------------

    def print_layers(self) -> None:
        """Print a rich-formatted table of layers to stdout."""
        render_layers(
            image_name=self._image_name,
            total_size=self._attrs.get("Size", 0),
            layers=self.layers(),
        )

    def print_audit(self) -> None:
        """Print a rich-formatted audit summary to stdout."""
        render_audit(
            image_name=self._image_name,
            audit_results=self.audit(),
        )

    def print_diff(self, other: str) -> None:
        """Print a rich-formatted diff table to stdout.

        Args:
            other: The image name/tag to compare against.
        """
        entries = self.diff(other)
        render_diff(
            image_a=self._image_name,
            image_b=other,
            diff_entries=entries,
        )
