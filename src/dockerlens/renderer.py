"""Rich-based terminal rendering helpers for dockerlens.

Provides formatted tables and panels for layer inspection, audit
results, and filesystem diffs. These are purely cosmetic and have
no effect on the library's data-processing logic.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dockerlens.models import AuditResult, DiffEntry, Layer

_console = Console()

# Severity → (icon, style) mappings for audit output
_SEVERITY_STYLES: dict[str, tuple[str, str]] = {
    "ERROR": ("🔴", "bold red"),
    "WARNING": ("⚠ ", "yellow"),
    "INFO": ("ℹ ", "cyan"),
}

# Change type → (icon, style) mappings for diff output
_CHANGE_STYLES: dict[str, tuple[str, str]] = {
    "added": ("+", "green"),
    "removed": ("-", "red"),
    "modified": ("~", "yellow"),
}


def _format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"  # pragma: no cover


def render_layers(
    image_name: str,
    total_size: int,
    layers: list[Layer],
) -> None:
    """Print a rich-formatted table of image layers.

    Args:
        image_name: Display name of the image.
        total_size: Total image size in bytes.
        layers: Ordered list of Layer objects.
    """
    header = f"  {image_name} — {len(layers)} layers, {_format_size(total_size)} total"
    _console.print(Panel(header, style="bold blue"))

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Digest", width=14)
    table.add_column("Size", width=12, justify="right")
    table.add_column("Command", overflow="fold")

    for layer in layers:
        # Truncate digest for display
        digest_short = layer.digest[:14] if layer.digest != "<none>" else "<none>"
        table.add_row(
            str(layer.index),
            digest_short,
            layer.size_human,
            layer.command,
        )

    _console.print(table)


def render_audit(
    image_name: str,
    audit_results: list[AuditResult],
) -> None:
    """Print a rich-formatted audit summary.

    Args:
        image_name: Display name of the image.
        audit_results: List of AuditResult objects.
    """
    count = len(audit_results)
    noun = "finding" if count == 1 else "findings"
    header = f"  Audit: {image_name} — {count} {noun}"

    if count == 0:
        _console.print(Panel(header, style="bold green"))
        _console.print("  ✅ No issues found!", style="green")
        return

    _console.print(Panel(header, style="bold yellow"))

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Icon", width=3)
    table.add_column("Severity", width=10)
    table.add_column("Rule", width=26)
    table.add_column("Message", overflow="fold")

    for result in audit_results:
        icon, style = _SEVERITY_STYLES.get(result.severity, ("?", "white"))
        table.add_row(
            icon,
            f"[{style}]{result.severity}[/{style}]",
            f"[bold]{result.rule_id}[/bold]",
            result.message,
        )

    _console.print(table)


def render_diff(
    image_a: str,
    image_b: str,
    diff_entries: list[DiffEntry],
) -> None:
    """Print a rich-formatted diff table.

    Args:
        image_a: Display name of the first image.
        image_b: Display name of the second image.
        diff_entries: List of DiffEntry objects.
    """
    count = len(diff_entries)
    noun = "change" if count == 1 else "changes"
    header = f"  Diff: {image_a} → {image_b} — {count} {noun}"

    if count == 0:
        _console.print(Panel(header, style="bold green"))
        _console.print("  ✅ Images are identical!", style="green")
        return

    _console.print(Panel(header, style="bold magenta"))

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("", width=3)
    table.add_column("Path", overflow="fold")
    table.add_column("Type", width=10)
    table.add_column("Size", width=20)

    for entry in diff_entries:
        icon, style = _CHANGE_STYLES.get(entry.change_type, ("?", "white"))

        # Format the size column
        if entry.change_type == "added":
            size_str = _format_size(entry.size_after or 0)
        elif entry.change_type == "removed":
            size_str = _format_size(entry.size_before or 0)
        else:
            before = _format_size(entry.size_before or 0)
            after = _format_size(entry.size_after or 0)
            size_str = f"{before} → {after}"

        table.add_row(
            f"[{style}]{icon}[/{style}]",
            entry.path,
            f"[{style}]{entry.change_type}[/{style}]",
            size_str,
        )

    _console.print(table)
