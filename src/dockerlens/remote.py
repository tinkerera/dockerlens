"""Module for communicating with the Docker Hub Registry API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from dockerlens.exceptions import RemoteRegistryError


def fetch_remote_image_data(
    image_ref: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch image metadata directly from Docker Hub without pulling it.

    Args:
        image_ref: The image name and optionally tag, e.g. "nginx:latest" or "ubuntu".

    Returns:
        A tuple of (attrs, history) matching the format expected by ImageAnalyzer.
    """
    if ":" in image_ref:
        repo, tag = image_ref.split(":")
    else:
        repo, tag = image_ref, "latest"

    # Normalize repo name for Docker Hub
    if "/" not in repo:
        repo = f"library/{repo}"

    try:
        # 1. Fetch anonymous authentication token
        token_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
        req = urllib.request.Request(token_url)
        with urllib.request.urlopen(req) as response:
            token_data = json.loads(response.read().decode())
            token = token_data["token"]

        # 2. Fetch the manifest
        manifest_url = f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}"
        req = urllib.request.Request(manifest_url)
        req.add_header("Authorization", f"Bearer {token}")
        # Request V2 and OCI manifest types. Manifest lists are for multi-arch.
        req.add_header(
            "Accept",
            "application/vnd.docker.distribution.manifest.v2+json, "
            "application/vnd.oci.image.manifest.v1+json, "
            "application/vnd.docker.distribution.manifest.list.v2+json",
        )

        with urllib.request.urlopen(req) as response:
            manifest = json.loads(response.read().decode())

        # If it's a manifest list (multi-arch), pick linux/amd64 or the first one
        if "manifests" in manifest:
            chosen_digest = None
            for m in manifest["manifests"]:
                platform = m.get("platform", {})
                if platform.get("os") == "linux" and platform.get("architecture") in [
                    "amd64",
                    "arm64",
                ]:
                    chosen_digest = m["digest"]
                    break
            if not chosen_digest:
                chosen_digest = manifest["manifests"][0]["digest"]

            # Fetch the actual manifest
            req = urllib.request.Request(
                f"https://registry-1.docker.io/v2/{repo}/manifests/{chosen_digest}"
            )
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header(
                "Accept",
                "application/vnd.docker.distribution.manifest.v2+json, "
                "application/vnd.oci.image.manifest.v1+json",
            )
            with urllib.request.urlopen(req) as response:
                manifest = json.loads(response.read().decode())

        # Extract config digest and layer sizes
        config_digest = manifest.get("config", {}).get("digest")
        if not config_digest:
            raise RemoteRegistryError(
                f"Could not find config digest for image {image_ref!r}"
            )

        layer_sizes = [layer.get("size", 0) for layer in manifest.get("layers", [])]

        # 3. Fetch the configuration blob
        blob_url = f"https://registry-1.docker.io/v2/{repo}/blobs/{config_digest}"
        req = urllib.request.Request(blob_url)
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as response:
            config_blob = json.loads(response.read().decode())

        # 4. Translate OCI format to local Docker SDK format
        attrs = {
            "Id": config_digest,
            "Size": sum(layer_sizes),
            "Config": config_blob.get("config", {}),
            "RootFS": config_blob.get("rootfs", {}),
            "RepoTags": [image_ref],
        }

        # Remote history is base-to-top. Local history() is top-to-base (newest first).
        raw_history = config_blob.get("history", [])

        # We need to map the flat layer_sizes array to history entries.
        # History entries with empty_layer=False consume one layer_size.
        layer_idx = 0
        translated_history = []

        for entry in raw_history:
            size = 0
            is_empty = entry.get("empty_layer", False)
            if not is_empty and layer_idx < len(layer_sizes):
                size = layer_sizes[layer_idx]
                layer_idx += 1

            translated_history.append(
                {
                    "CreatedBy": entry.get("created_by", ""),
                    "Size": size,
                    "Created": entry.get("created", ""),
                    "Id": "<missing>"
                    if is_empty
                    else "sha256:unknown",  # exact ID doesn't matter for audit
                }
            )

        # Reverse to make it newest-first
        translated_history.reverse()

        return attrs, translated_history

    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            raise RemoteRegistryError(
                f"Image {image_ref!r} not found on Docker Hub."
            ) from e
        raise RemoteRegistryError(f"Registry HTTP error: {e}") from e
    except Exception as e:
        raise RemoteRegistryError(f"Failed to fetch remote image data: {e}") from e
