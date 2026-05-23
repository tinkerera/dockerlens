"""dockerlens — Programmatic Docker image layer analysis, auditing, and diffing.

This package provides a clean, typed Python API for inspecting Docker
images without shelling out to CLI tools.

Example::

    from dockerlens import ImageAnalyzer

    analyzer = ImageAnalyzer("nginx:latest")
    for layer in analyzer.layers():
        print(f"{layer.index}: {layer.size_human}  {layer.command}")

    for issue in analyzer.audit():
        print(f"[{issue.severity}] {issue.rule_id}: {issue.message}")
"""

from __future__ import annotations

from dockerlens.analyzer import ImageAnalyzer
from dockerlens.exceptions import DockerLensError, DockerNotAvailable, ImageNotFound
from dockerlens.models import AuditResult, DiffEntry, ImageReport, Layer

__all__ = [
    "ImageAnalyzer",
    "Layer",
    "AuditResult",
    "DiffEntry",
    "ImageReport",
    "DockerLensError",
    "DockerNotAvailable",
    "ImageNotFound",
]

__version__ = "0.1.0"
