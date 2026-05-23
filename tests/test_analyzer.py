"""Tests for dockerlens.analyzer.ImageAnalyzer."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import docker.errors
import pytest

from dockerlens.analyzer import ImageAnalyzer
from dockerlens.exceptions import DockerNotAvailable, ImageNotFound
from dockerlens.models import ImageReport, Layer


class TestImageAnalyzerInit:
    """Tests for ImageAnalyzer construction and error handling."""

    def test_docker_not_available_raises(self, mock_docker_client: MagicMock) -> None:
        mock_docker_client.images.get.side_effect = docker.errors.DockerException(
            "Connection refused"
        )
        with pytest.raises(DockerNotAvailable):
            ImageAnalyzer("nginx:latest", docker_client=mock_docker_client)

    def test_image_not_found_raises(self, mock_docker_client: MagicMock) -> None:
        mock_docker_client.images.get.side_effect = docker.errors.ImageNotFound(
            "not found"
        )
        with pytest.raises(ImageNotFound) as exc_info:
            ImageAnalyzer("nonexistent:v1", docker_client=mock_docker_client)
        assert "nonexistent:v1" in str(exc_info.value)

    def test_successful_init(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        image_mock = MagicMock()
        type(image_mock).attrs = PropertyMock(return_value=mock_image_inspect)
        image_mock.history.return_value = mock_image_history
        mock_docker_client.images.get.return_value = image_mock

        analyzer = ImageAnalyzer("nginx:latest", docker_client=mock_docker_client)
        assert analyzer._image_name == "nginx:latest"


class TestLayers:
    """Tests for ImageAnalyzer.layers()."""

    def _make_analyzer(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> ImageAnalyzer:
        image_mock = MagicMock()
        type(image_mock).attrs = PropertyMock(return_value=mock_image_inspect)
        image_mock.history.return_value = mock_image_history
        mock_docker_client.images.get.return_value = image_mock
        return ImageAnalyzer("nginx:latest", docker_client=mock_docker_client)

    def test_layers_count(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        analyzer = self._make_analyzer(
            mock_docker_client, mock_image_inspect, mock_image_history
        )
        layers = analyzer.layers()
        assert len(layers) == 3

    def test_layers_order(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        analyzer = self._make_analyzer(
            mock_docker_client, mock_image_inspect, mock_image_history
        )
        layers = analyzer.layers()
        # Index 0 should be the base layer (ADD file)
        assert layers[0].index == 0
        assert "ADD" in layers[0].command
        # Index 2 should be the top layer (CMD)
        assert layers[2].index == 2
        assert "CMD" in layers[2].command

    def test_layers_sizes(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        analyzer = self._make_analyzer(
            mock_docker_client, mock_image_inspect, mock_image_history
        )
        layers = analyzer.layers()
        assert layers[0].size_bytes == 80_000_000
        assert layers[1].size_bytes == 40_000_000
        assert layers[2].size_bytes == 0

    def test_layers_are_layer_instances(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        analyzer = self._make_analyzer(
            mock_docker_client, mock_image_inspect, mock_image_history
        )
        layers = analyzer.layers()
        for layer in layers:
            assert isinstance(layer, Layer)

    def test_layers_timestamps_are_iso(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        analyzer = self._make_analyzer(
            mock_docker_client, mock_image_inspect, mock_image_history
        )
        layers = analyzer.layers()
        for layer in layers:
            # ISO 8601 timestamps contain "T" and timezone info
            assert "T" in layer.created_at


class TestReport:
    """Tests for ImageAnalyzer.report()."""

    def test_report_returns_image_report(
        self,
        mock_docker_client: MagicMock,
        mock_image_inspect: dict,  # type: ignore[type-arg]
        mock_image_history: list[dict],  # type: ignore[type-arg]
    ) -> None:
        image_mock = MagicMock()
        type(image_mock).attrs = PropertyMock(return_value=mock_image_inspect)
        image_mock.history.return_value = mock_image_history
        mock_docker_client.images.get.return_value = image_mock

        analyzer = ImageAnalyzer("nginx:latest", docker_client=mock_docker_client)
        report = analyzer.report()

        assert isinstance(report, ImageReport)
        assert report.image_name == "nginx:latest"
        assert report.image_id == "sha256:abc123def456"
        assert report.total_size_bytes == 142_000_000
        assert len(report.layers) == 3
