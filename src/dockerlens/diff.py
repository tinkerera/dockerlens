"""Diff engine — filesystem-level comparison of two Docker images.

Exports both images as tar streams, parses the overlay filesystem
(including whiteout files), and produces a list of :class:`DiffEntry`
objects describing added, removed, and modified files.
"""

from __future__ import annotations

import io
import os
import tarfile
from collections.abc import Sequence
from typing import IO, Any

from dockerlens.models import DiffEntry

# Docker overlay whiteout prefix — a file named ``.wh.<name>`` in a
# layer means that ``<name>`` was deleted in that layer.
_WHITEOUT_PREFIX = ".wh."

# Opaque whiteout marker — a file named ``.wh..wh..opq`` means the
# entire containing directory was replaced in this layer.
_OPAQUE_WHITEOUT = ".wh..wh..opq"


class DiffEngine:
    """Compares the filesystems of two Docker images.

    Args:
        image_a: A Docker SDK ``Image`` object for the first image.
        image_b: A Docker SDK ``Image`` object for the second image.
    """

    def __init__(self, image_a: Any, image_b: Any) -> None:
        self._image_a = image_a
        self._image_b = image_b

    def compare(
        self,
        include_paths: Sequence[str] | None = None,
        exclude_paths: Sequence[str] | None = None,
    ) -> list[DiffEntry]:
        """Compare the two images and return filesystem differences.

        Args:
            include_paths: If provided, only report changes under these
                path prefixes.
            exclude_paths: If provided, exclude changes under these
                path prefixes.

        Returns:
            A sorted list of :class:`DiffEntry` instances.
        """
        fs_a = self._build_filesystem(self._image_a)
        fs_b = self._build_filesystem(self._image_b)

        entries: list[DiffEntry] = []

        # Files only in A → removed
        for path in sorted(fs_a.keys() - fs_b.keys()):
            entries.append(
                DiffEntry(
                    path=path,
                    change_type="removed",
                    size_before=fs_a[path],
                    size_after=None,
                )
            )

        # Files only in B → added
        for path in sorted(fs_b.keys() - fs_a.keys()):
            entries.append(
                DiffEntry(
                    path=path,
                    change_type="added",
                    size_before=None,
                    size_after=fs_b[path],
                )
            )

        # Files in both but with different sizes → modified
        for path in sorted(fs_a.keys() & fs_b.keys()):
            if fs_a[path] != fs_b[path]:
                entries.append(
                    DiffEntry(
                        path=path,
                        change_type="modified",
                        size_before=fs_a[path],
                        size_after=fs_b[path],
                    )
                )

        # Apply path filters
        if include_paths:
            prefixes = tuple(include_paths)
            entries = [e for e in entries if e.path.startswith(prefixes)]
        if exclude_paths:
            prefixes_excl = tuple(exclude_paths)
            entries = [e for e in entries if not e.path.startswith(prefixes_excl)]

        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_filesystem(image: Any) -> dict[str, int]:
        """Export an image and build its effective filesystem dict.

        Processes all layers in order, applying whiteout semantics to
        simulate the union filesystem that Docker uses at runtime.

        Args:
            image: A Docker SDK ``Image`` object.

        Returns:
            A dict mapping absolute file paths to their sizes (in bytes).
        """
        fs: dict[str, int] = {}

        # image.save() returns a generator of bytes chunks
        raw_chunks: list[bytes] = []
        for chunk in image.save():
            raw_chunks.append(chunk)

        image_tar_bytes = b"".join(raw_chunks)
        image_tar_stream = io.BytesIO(image_tar_bytes)

        with tarfile.open(fileobj=image_tar_stream, mode="r") as outer_tar:
            # Docker image tars contain a directory per layer, each
            # containing a ``layer.tar`` with the actual filesystem diff.
            layer_tar_names = sorted(
                name
                for name in outer_tar.getnames()
                if name.endswith("/layer.tar") or name == "layer.tar"
            )

            for layer_tar_name in layer_tar_names:
                layer_member = outer_tar.getmember(layer_tar_name)
                layer_fileobj = outer_tar.extractfile(layer_member)
                if layer_fileobj is None:
                    continue  # pragma: no cover

                DiffEngine._process_layer_tar(layer_fileobj, fs)

        return fs

    @staticmethod
    def _process_layer_tar(
        layer_fileobj: IO[bytes],
        fs: dict[str, int],
    ) -> None:
        """Process a single layer tar and update the filesystem dict.

        Handles regular files, whiteout files (``.wh.``), and opaque
        whiteout markers (``.wh..wh..opq``).

        Args:
            layer_fileobj: File-like object for the layer tar.
            fs: The cumulative filesystem dict to update in-place.
        """
        with tarfile.open(fileobj=layer_fileobj, mode="r") as layer_tar:
            for member in layer_tar.getmembers():
                name = member.name

                # Normalize: strip leading "./" or "/"
                if name.startswith("./"):
                    name = name[2:]
                if not name.startswith("/"):
                    name = "/" + name

                basename = os.path.basename(name)
                dirname = os.path.dirname(name)

                # Handle opaque whiteout — entire directory was replaced
                if basename == _OPAQUE_WHITEOUT:
                    # Remove all entries under this directory
                    to_remove = [p for p in fs if p.startswith(dirname + "/")]
                    for p in to_remove:
                        del fs[p]
                    continue

                # Handle regular whiteout — specific file was deleted
                if basename.startswith(_WHITEOUT_PREFIX):
                    original_name = basename[len(_WHITEOUT_PREFIX) :]
                    original_path = os.path.join(dirname, original_name)
                    fs.pop(original_path, None)
                    continue

                # Skip directories — we only track files
                if member.isdir():
                    continue

                # Regular file — add or update
                fs[name] = member.size
