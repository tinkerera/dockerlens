"""Tests for dockerlens.cli."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dockerlens.cli import main
from dockerlens.exceptions import DockerLensError


@patch("dockerlens.cli.ImageAnalyzer")
def test_cli_analyze_text(mock_analyzer_class: MagicMock) -> None:
    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    exit_code = main(["analyze", "nginx:latest"])
    assert exit_code == 0

    mock_analyzer_class.assert_called_once_with("nginx:latest", remote=False)
    mock_analyzer.print_layers.assert_called_once()
    mock_analyzer.print_audit.assert_called_once()


@patch("dockerlens.cli.ImageAnalyzer")
def test_cli_analyze_json(
    mock_analyzer_class: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_analyzer = MagicMock()
    mock_report = MagicMock()
    mock_report.to_json.return_value = '{"test": "json"}'
    mock_analyzer.report.return_value = mock_report
    mock_analyzer_class.return_value = mock_analyzer

    exit_code = main(["analyze", "nginx:latest", "--format", "json"])
    assert exit_code == 0

    mock_analyzer_class.assert_called_once_with("nginx:latest", remote=False)
    mock_analyzer.report.assert_called_once()
    mock_report.to_json.assert_called_once()

    captured = capsys.readouterr()
    assert '{"test": "json"}' in captured.out


@patch("dockerlens.cli.ImageAnalyzer")
def test_cli_analyze_remote(mock_analyzer_class: MagicMock) -> None:
    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    exit_code = main(["analyze", "--remote", "nginx:latest"])
    assert exit_code == 0

    mock_analyzer_class.assert_called_once_with("nginx:latest", remote=True)
    mock_analyzer.print_layers.assert_called_once()
    mock_analyzer.print_audit.assert_called_once()


@patch("dockerlens.cli.ImageAnalyzer")
def test_cli_diff(mock_analyzer_class: MagicMock) -> None:
    mock_analyzer = MagicMock()
    mock_analyzer_class.return_value = mock_analyzer

    exit_code = main(["diff", "nginx:1.24", "nginx:latest"])
    assert exit_code == 0

    mock_analyzer_class.assert_called_once_with("nginx:1.24")
    mock_analyzer.print_diff.assert_called_once_with("nginx:latest")


@patch("dockerlens.cli.ImageAnalyzer")
def test_cli_handles_error(
    mock_analyzer_class: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_analyzer_class.side_effect = DockerLensError("Image not found")

    exit_code = main(["analyze", "nonexistent:latest"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Image not found" in captured.err
