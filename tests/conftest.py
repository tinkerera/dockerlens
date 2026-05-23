"""Shared pytest fixtures for dockerlens tests.

All fixtures use MagicMock to simulate Docker SDK responses so that
tests never require a running Docker daemon.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_docker_client() -> MagicMock:
    """Return a MagicMock simulating ``docker.DockerClient``."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_image_inspect() -> dict:  # type: ignore[type-arg]
    """Minimal realistic image inspect payload (nginx-like)."""
    return {
        "Id": "sha256:abc123def456",
        "RepoTags": ["nginx:latest"],
        "Size": 142_000_000,
        "RootFS": {
            "Type": "layers",
            "Layers": [
                "sha256:layer1digest",
                "sha256:layer2digest",
                "sha256:layer3digest",
            ],
        },
        "Config": {
            "User": "",
            "Env": ["PATH=/usr/local/sbin:/usr/local/bin"],
        },
    }


@pytest.fixture
def mock_image_history() -> list[dict]:  # type: ignore[type-arg]
    """Three-layer image history (newest-first, as the Docker SDK returns)."""
    return [
        {
            "Id": "sha256:layer3digest",
            "CreatedBy": '/bin/sh -c #(nop)  CMD ["nginx", "-g", "daemon off;"]',
            "Size": 0,
            "Created": 1700000200,
        },
        {
            "Id": "sha256:layer2digest",
            "CreatedBy": "/bin/sh -c apt-get install -y curl",
            "Size": 40_000_000,
            "Created": 1700000100,
        },
        {
            "Id": "sha256:layer1digest",
            "CreatedBy": "/bin/sh -c #(nop) ADD file:abc123 in /",
            "Size": 80_000_000,
            "Created": 1700000000,
        },
    ]
