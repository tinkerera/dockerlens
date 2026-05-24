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

    def to_markdown(self) -> str:
        """Serialize to a Markdown formatted string.
        
        Returns:
            A string containing Markdown headers and tables.
        """
        lines = [
            f"# Image Report: `{self.image_name}`",
            f"- **Image ID:** `{self.image_id}`",
            f"- **Total Size:** {self.total_size_bytes} bytes",
            "",
            "## Audit Results"
        ]
        if not self.audit_results:
            lines.append("No issues found! ✅")
        else:
            lines.append("| Severity | Rule | Message | Layer |")
            lines.append("|---|---|---|---|")
            for r in self.audit_results:
                layer_str = str(r.layer_index) if r.layer_index is not None else "-"
                lines.append(f"| **{r.severity}** | `{r.rule_id}` | {r.message} | {layer_str} |")
        
        lines.append("")
        lines.append("## Layers")
        lines.append("| Index | Size | Command |")
        lines.append("|---|---|---|")
        for layer in self.layers:
            # truncate command if it's too long for markdown table
            cmd = layer.command.replace('|', '\\|')
            if len(cmd) > 100:
                cmd = cmd[:97] + "..."
            lines.append(f"| {layer.index} | {layer.size_human} | `{cmd}` |")
            
        return "\\n".join(lines) + "\\n"

    def to_html(self) -> str:
        """Serialize to an HTML formatted string.
        
        Returns:
            A string containing HTML representation of the report.
        """
        html = [
            f"<h1>Image Report: <code>{self.image_name}</code></h1>",
            "<ul>",
            f"<li><b>Image ID:</b> <code>{self.image_id}</code></li>",
            f"<li><b>Total Size:</b> {self.total_size_bytes} bytes</li>",
            "</ul>",
            "<h2>Audit Results</h2>"
        ]
        if not self.audit_results:
            html.append("<p>No issues found! ✅</p>")
        else:
            html.append("<table border='1'><tr><th>Severity</th><th>Rule</th><th>Message</th><th>Layer</th></tr>")
            for r in self.audit_results:
                layer_str = str(r.layer_index) if r.layer_index is not None else "-"
                html.append(f"<tr><td><b>{r.severity}</b></td><td><code>{r.rule_id}</code></td><td>{r.message}</td><td>{layer_str}</td></tr>")
            html.append("</table>")
            
        html.append("<h2>Layers</h2>")
        html.append("<table border='1'><tr><th>Index</th><th>Size</th><th>Command</th></tr>")
        for layer in self.layers:
            cmd = layer.command.replace("<", "&lt;").replace(">", "&gt;")
            if len(cmd) > 100:
                cmd = cmd[:97] + "..."
            html.append(f"<tr><td>{layer.index}</td><td>{layer.size_human}</td><td><code>{cmd}</code></td></tr>")
        html.append("</table>")
        
        return "\\n".join(html) + "\\n"
