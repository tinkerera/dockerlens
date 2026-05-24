"""Audit engine — pattern-based best-practice checks for Docker images.

Each audit rule is implemented as a private method on :class:`AuditEngine`.
The engine iterates over all rules and collects :class:`AuditResult` objects.
"""

from __future__ import annotations

import re

from dockerlens.models import AuditResult

# Threshold for the LARGE_LAYER rule (200 MB)
_LARGE_LAYER_THRESHOLD: int = 200 * 1024 * 1024

# Threshold for the MANY_LAYERS rule
_MANY_LAYERS_THRESHOLD: int = 20

# Regex pattern for common secret environment variables
_SECRET_PATTERN: re.Pattern[str] = re.compile(
    r"ENV\s+\S*(PASSWORD|SECRET|API_KEY|TOKEN)\b",
    re.IGNORECASE,
)


class AuditEngine:
    """Runs all built-in audit rules against Docker image metadata.

    Args:
        image_data: The image inspect dict (``image.attrs``).
        history: The image history list (``image.history()``), ordered
            newest-first as returned by the Docker SDK.
    """

    def __init__(
        self,
        image_data: dict,  # type: ignore[type-arg]
        history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        self.image_data = image_data
        self.history = history

    def run_all(self) -> list[AuditResult]:
        """Execute every audit rule and return combined results."""
        results: list[AuditResult] = []
        results.extend(self._check_no_user())
        results.extend(self._check_apt_cache())
        results.extend(self._check_latest_tag())
        results.extend(self._check_large_layers())
        results.extend(self._check_add_instruction())
        results.extend(self._check_secret_patterns())
        results.extend(self._check_many_layers())
        results.extend(self._check_curl_bash())
        results.extend(self._check_expose_ssh())
        results.extend(self._check_apk_cache())
        results.extend(self._check_pip_cache())
        return results

    # ------------------------------------------------------------------
    # Individual audit rules
    # ------------------------------------------------------------------

    def _check_no_user(self) -> list[AuditResult]:
        """NO_USER — warn if the image has no USER instruction."""
        config = self.image_data.get("Config", {})
        user: str = config.get("User", "")

        if user:
            return []

        # Also check history for a USER instruction
        for entry in self.history:
            created_by: str = entry.get("CreatedBy", "")
            if "USER" in created_by and "#(nop)" in created_by:
                return []

        return [
            AuditResult(
                rule_id="NO_USER",
                severity="WARNING",
                message="Container runs as root (no USER instruction found)",
            )
        ]

    def _check_apt_cache(self) -> list[AuditResult]:
        """APT_CACHE_NOT_CLEARED — warn if apt cache is not cleaned."""
        results: list[AuditResult] = []
        # History is newest-first; iterate in reverse for natural layer order
        reversed_history = list(reversed(self.history))

        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "")

            if "apt-get" not in created_by and "apt " not in created_by:
                continue

            has_install = "apt-get install" in created_by or "apt install" in created_by
            if not has_install:
                continue

            has_cleanup = (
                "rm -rf /var/lib/apt/lists" in created_by
                or "rm -r /var/lib/apt/lists" in created_by
                or "apt-get clean" in created_by
            )

            if not has_cleanup:
                results.append(
                    AuditResult(
                        rule_id="APT_CACHE_NOT_CLEARED",
                        severity="WARNING",
                        message=(f"apt cache not cleared after install in layer {i}"),
                        layer_index=i,
                    )
                )

        return results

    def _check_latest_tag(self) -> list[AuditResult]:
        """LATEST_TAG — info if the image uses the 'latest' tag."""
        repo_tags: list[str] = self.image_data.get("RepoTags", []) or []

        for tag in repo_tags:
            if tag.endswith(":latest"):
                return [
                    AuditResult(
                        rule_id="LATEST_TAG",
                        severity="INFO",
                        message=(
                            f"Image uses the 'latest' tag ({tag}), "
                            "making builds non-reproducible"
                        ),
                    )
                ]
        return []

    def _check_large_layers(self) -> list[AuditResult]:
        """LARGE_LAYER — info if any layer exceeds 200 MB."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))

        for i, entry in enumerate(reversed_history):
            size: int = entry.get("Size", 0)
            if size > _LARGE_LAYER_THRESHOLD:
                size_mb = size / (1024 * 1024)
                results.append(
                    AuditResult(
                        rule_id="LARGE_LAYER",
                        severity="INFO",
                        message=(
                            f"Layer {i} is {size_mb:.1f} MB. Consider "
                            "multi-stage builds or .dockerignore to reduce size"
                        ),
                        layer_index=i,
                    )
                )

        return results

    def _check_add_instruction(self) -> list[AuditResult]:
        """ADD_INSTEAD_OF_COPY — info if ADD is used instead of COPY."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))

        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "")

            # Docker history represents ADD as:
            #   /bin/sh -c #(nop) ADD file:<hash> in /
            # We want to match the real ADD instruction, not RUN commands
            # that happen to contain the word "add".
            if "#(nop) ADD" in created_by.upper() or (
                "#(nop)" in created_by and "ADD " in created_by
            ):
                results.append(
                    AuditResult(
                        rule_id="ADD_INSTEAD_OF_COPY",
                        severity="INFO",
                        message=(
                            f"Layer {i} uses ADD instead of COPY. ADD has "
                            "implicit tar extraction and URL fetching that "
                            "may be unintended"
                        ),
                        layer_index=i,
                    )
                )

        return results

    def _check_secret_patterns(self) -> list[AuditResult]:
        """SECRET_PATTERN — error if env vars suggest hardcoded secrets."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))

        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "")

            if _SECRET_PATTERN.search(created_by):
                results.append(
                    AuditResult(
                        rule_id="SECRET_PATTERN",
                        severity="ERROR",
                        message=(
                            f"Layer {i} may contain hardcoded secrets "
                            f"in environment variables"
                        ),
                        layer_index=i,
                    )
                )

        return results

    def _check_many_layers(self) -> list[AuditResult]:
        """MANY_LAYERS — info if the image has more than 20 layers."""
        layer_count = len(self.history)
        if layer_count > _MANY_LAYERS_THRESHOLD:
            return [
                AuditResult(
                    rule_id="MANY_LAYERS",
                    severity="INFO",
                    message=(
                        f"Image has {layer_count} layers (threshold: "
                        f"{_MANY_LAYERS_THRESHOLD}). Consider combining "
                        "RUN commands to reduce layer count"
                    ),
                )
            ]
        return []

    def _check_curl_bash(self) -> list[AuditResult]:
        """CURL_BASH_PATTERN — warning if curl/wget is piped to bash/sh."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))
        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "").lower()
            if ("curl" in created_by or "wget" in created_by) and ("| bash" in created_by or "| sh" in created_by):
                results.append(
                    AuditResult(
                        rule_id="CURL_BASH_PATTERN",
                        severity="WARNING",
                        message=(
                            f"Layer {i} pipes curl/wget to bash or sh. "
                            "This is a security risk and hurts reproducibility."
                        ),
                        layer_index=i,
                    )
                )
        return results

    def _check_expose_ssh(self) -> list[AuditResult]:
        """EXPOSED_SSH_PORT — warning if SSH port 22 is exposed."""
        config = self.image_data.get("Config", {})
        exposed_ports = config.get("ExposedPorts", {})
        if "22/tcp" in exposed_ports or "22/udp" in exposed_ports:
            return [
                AuditResult(
                    rule_id="EXPOSED_SSH_PORT",
                    severity="WARNING",
                    message="Port 22 (SSH) is exposed. Running SSH in containers is usually an anti-pattern."
                )
            ]
        return []

    def _check_apk_cache(self) -> list[AuditResult]:
        """APK_NO_CACHE — warning if apk add is used without --no-cache."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))
        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "")
            if "apk add" in created_by and "--no-cache" not in created_by:
                results.append(
                    AuditResult(
                        rule_id="APK_NO_CACHE",
                        severity="WARNING",
                        message=f"Layer {i} uses 'apk add' without '--no-cache', inflating image size.",
                        layer_index=i,
                    )
                )
        return results

    def _check_pip_cache(self) -> list[AuditResult]:
        """PIP_NO_CACHE_DIR — warning if pip install is used without --no-cache-dir."""
        results: list[AuditResult] = []
        reversed_history = list(reversed(self.history))
        for i, entry in enumerate(reversed_history):
            created_by: str = entry.get("CreatedBy", "")
            if "pip install" in created_by and "--no-cache-dir" not in created_by:
                results.append(
                    AuditResult(
                        rule_id="PIP_NO_CACHE_DIR",
                        severity="WARNING",
                        message=f"Layer {i} uses 'pip install' without '--no-cache-dir', inflating image size.",
                        layer_index=i,
                    )
                )
        return results
