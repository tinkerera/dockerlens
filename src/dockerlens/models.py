"""Data models for dockerlens.

All public return types are defined as dataclasses. These are the building
blocks used by every other module in the library.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class Layer:
    """Represents a single layer in a Docker image.

    Attributes:
        index: 0-based layer order (0 = base image layer).
        digest: sha256 digest of the layer tar.
        size_bytes: Uncompressed size of the layer in bytes.
        command: The Dockerfile instruction that created this layer.
        created_at: ISO 8601 timestamp of when the layer was created.
    """

    index: int
    digest: str
    size_bytes: int
    command: str
    created_at: str

    @property
    def size_human(self) -> str:
        """Return size as a human-readable string, e.g. '12.4 MB'."""
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0 or unit == "TB":
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024.0
        # Unreachable, but satisfies type checker
        return f"{size:.1f} TB"  # pragma: no cover


@dataclass
class AuditResult:
    """Represents a single audit finding.

    Attributes:
        rule_id: Machine-readable identifier, e.g. ``"NO_USER"``.
        severity: One of ``"ERROR"``, ``"WARNING"``, or ``"INFO"``.
        message: Human-readable description of the finding.
        layer_index: Which layer triggered the issue, if applicable.
    """

    rule_id: str
    severity: str
    message: str
    layer_index: int | None = None


@dataclass
class DiffEntry:
    """Represents a single filesystem difference between two images.

    Attributes:
        path: Absolute file path inside the container.
        change_type: One of ``"added"``, ``"removed"``, or ``"modified"``.
        size_before: File size in the first image (``None`` if added).
        size_after: File size in the second image (``None`` if removed).
    """

    path: str
    change_type: str
    size_before: int | None = None
    size_after: int | None = None


@dataclass
class ImageReport:
    """Full analysis report for a Docker image.

    Combines layer information and audit results into a single object
    that can be serialized to JSON for CI consumption.

    Attributes:
        image_name: The image name/tag that was analyzed.
        image_id: The sha256 image ID.
        total_size_bytes: Total uncompressed image size in bytes.
        layers: Ordered list of image layers.
        audit_results: List of audit findings (empty if no issues).
    """

    image_name: str
    image_id: str
    total_size_bytes: int
    layers: list[Layer] = field(default_factory=list)
    audit_results: list[AuditResult] = field(default_factory=list)

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialize to a plain dict suitable for JSON export."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a formatted JSON string.

        Args:
            indent: Number of spaces for JSON indentation. Defaults to 2.

        Returns:
            A JSON string representation of the report.
        """
        return json.dumps(self.to_dict(), indent=indent)
