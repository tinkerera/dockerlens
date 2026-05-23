"""Tests for dockerlens.diff.DiffEngine.

All tests construct in-memory tar streams to simulate Docker image
exports, so no Docker daemon is needed.
"""

from __future__ import annotations

import io
import tarfile
from unittest.mock import MagicMock

from dockerlens.diff import DiffEngine


def _make_layer_tar(files: dict[str, bytes]) -> bytes:
    """Create an in-memory layer tar containing the given files.

    Args:
        files: Mapping of file paths to their contents.

    Returns:
        Raw bytes of the tar archive.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path, content in files.items():
            # Remove leading slash for tar member names
            name = path.lstrip("/")
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _make_image_tar(layers: list[bytes]) -> bytes:
    """Create an in-memory Docker image tar containing the given layers.

    Docker image tars have a directory per layer, each containing a
    ``layer.tar`` file.

    Args:
        layers: List of layer tar bytes, in order from base to top.

    Returns:
        Raw bytes of the outer image tar.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as outer:
        for i, layer_bytes in enumerate(layers):
            # Create a directory entry for the layer
            dir_name = f"{i:032x}/"
            dir_info = tarfile.TarInfo(name=dir_name)
            dir_info.type = tarfile.DIRTYPE
            outer.addfile(dir_info)

            # Add the layer.tar inside the directory
            member_name = f"{i:032x}/layer.tar"
            info = tarfile.TarInfo(name=member_name)
            info.size = len(layer_bytes)
            outer.addfile(info, io.BytesIO(layer_bytes))
    return buf.getvalue()


def _make_mock_image(image_tar_bytes: bytes) -> MagicMock:
    """Create a mock Docker image that yields tar bytes from save()."""
    image = MagicMock()
    # image.save() returns a generator of byte chunks
    image.save.return_value = iter([image_tar_bytes])
    return image


class TestDiffEngineBasics:
    """Basic diff tests: added, removed, modified files."""

    def test_added_file(self) -> None:
        layer_a = _make_layer_tar({"/etc/config": b"v1"})
        layer_b = _make_layer_tar({"/etc/config": b"v1", "/etc/newfile": b"new"})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()

        added = [e for e in entries if e.change_type == "added"]
        assert len(added) == 1
        assert added[0].path == "/etc/newfile"
        assert added[0].size_after == 3

    def test_removed_file(self) -> None:
        layer_a = _make_layer_tar({"/etc/config": b"v1", "/etc/oldfile": b"old"})
        layer_b = _make_layer_tar({"/etc/config": b"v1"})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()

        removed = [e for e in entries if e.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].path == "/etc/oldfile"
        assert removed[0].size_before == 3

    def test_modified_file(self) -> None:
        layer_a = _make_layer_tar({"/etc/config": b"short"})
        layer_b = _make_layer_tar({"/etc/config": b"much longer content"})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()

        modified = [e for e in entries if e.change_type == "modified"]
        assert len(modified) == 1
        assert modified[0].path == "/etc/config"
        assert modified[0].size_before == 5
        assert modified[0].size_after == 19

    def test_identical_images(self) -> None:
        layer = _make_layer_tar({"/etc/config": b"same"})
        tar_bytes = _make_image_tar([layer])

        image_a = _make_mock_image(tar_bytes)
        image_b = _make_mock_image(tar_bytes)

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()
        assert len(entries) == 0


class TestWhiteoutHandling:
    """Tests for overlay filesystem whiteout semantics."""

    def test_regular_whiteout_removes_file(self) -> None:
        # Image A: base layer has /app/config
        # Image B: base layer has /app/config, upper layer whiteouts it
        layer_a = _make_layer_tar({"/app/config": b"data"})

        layer_b_base = _make_layer_tar({"/app/config": b"data"})
        layer_b_upper = _make_layer_tar({"/app/.wh.config": b""})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b_base, layer_b_upper]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()

        # /app/config should show as removed in B
        removed = [e for e in entries if e.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].path == "/app/config"

        # The whiteout file itself should NOT appear in results
        paths = {e.path for e in entries}
        assert "/app/.wh.config" not in paths

    def test_opaque_whiteout_clears_directory(self) -> None:
        # Image A: /data/a.txt, /data/b.txt
        # Image B: opaque whiteout on /data/, then new /data/c.txt
        layer_a = _make_layer_tar(
            {
                "/data/a.txt": b"aaa",
                "/data/b.txt": b"bbb",
            }
        )

        layer_b_base = _make_layer_tar(
            {
                "/data/a.txt": b"aaa",
                "/data/b.txt": b"bbb",
            }
        )
        layer_b_opaque = _make_layer_tar(
            {
                "/data/.wh..wh..opq": b"",
                "/data/c.txt": b"ccc",
            }
        )

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b_base, layer_b_opaque]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare()

        removed = [e for e in entries if e.change_type == "removed"]
        added = [e for e in entries if e.change_type == "added"]

        removed_paths = {e.path for e in removed}
        added_paths = {e.path for e in added}

        assert "/data/a.txt" in removed_paths
        assert "/data/b.txt" in removed_paths
        assert "/data/c.txt" in added_paths


class TestPathFilters:
    """Tests for include_paths and exclude_paths filtering."""

    def test_include_paths(self) -> None:
        layer_a = _make_layer_tar({"/etc/a": b"1", "/var/b": b"2"})
        layer_b = _make_layer_tar({"/etc/a": b"1x", "/var/b": b"2x"})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare(include_paths=["/etc"])

        assert len(entries) == 1
        assert entries[0].path == "/etc/a"

    def test_exclude_paths(self) -> None:
        layer_a = _make_layer_tar({"/etc/a": b"1", "/var/b": b"2"})
        layer_b = _make_layer_tar({"/etc/a": b"1x", "/var/b": b"2x"})

        image_a = _make_mock_image(_make_image_tar([layer_a]))
        image_b = _make_mock_image(_make_image_tar([layer_b]))

        engine = DiffEngine(image_a, image_b)
        entries = engine.compare(exclude_paths=["/var"])

        assert len(entries) == 1
        assert entries[0].path == "/etc/a"
