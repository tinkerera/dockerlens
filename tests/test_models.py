"""Tests for dockerlens.models."""

from __future__ import annotations

import json

from dockerlens.models import AuditResult, DiffEntry, ImageReport, Layer


class TestLayerSizeHuman:
    """Tests for Layer.size_human property."""

    def test_zero_bytes(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=0,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "0 B"

    def test_small_bytes(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=512,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "512 B"

    def test_one_kilobyte(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=1024,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "1.0 KB"

    def test_kilobytes(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=1536,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "1.5 KB"

    def test_megabytes(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=1_572_864,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "1.5 MB"

    def test_gigabytes(self) -> None:
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=2_469_606_195,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "2.3 GB"

    def test_exact_boundary(self) -> None:
        # Exactly 1023 bytes — should remain in B
        layer = Layer(
            index=0,
            digest="sha256:abc",
            size_bytes=1023,
            command="CMD",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert layer.size_human == "1023 B"


class TestImageReport:
    """Tests for ImageReport serialization."""

    def test_to_dict_returns_dict(self) -> None:
        report = ImageReport(
            image_name="test:v1",
            image_id="sha256:abc",
            total_size_bytes=1000,
            layers=[
                Layer(
                    index=0,
                    digest="sha256:aaa",
                    size_bytes=1000,
                    command="CMD test",
                    created_at="2024-01-01T00:00:00+00:00",
                ),
            ],
            audit_results=[],
        )
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["image_name"] == "test:v1"
        assert len(d["layers"]) == 1

    def test_to_json_produces_valid_json(self) -> None:
        report = ImageReport(
            image_name="test:v1",
            image_id="sha256:abc",
            total_size_bytes=5000,
            layers=[
                Layer(
                    index=0,
                    digest="sha256:aaa",
                    size_bytes=3000,
                    command="RUN echo hello",
                    created_at="2024-01-01T00:00:00+00:00",
                ),
                Layer(
                    index=1,
                    digest="sha256:bbb",
                    size_bytes=2000,
                    command="CMD /bin/sh",
                    created_at="2024-01-01T01:00:00+00:00",
                ),
            ],
            audit_results=[
                AuditResult(rule_id="NO_USER", severity="WARNING", message="No user"),
            ],
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["image_name"] == "test:v1"
        assert len(parsed["layers"]) == 2
        assert len(parsed["audit_results"]) == 1

    def test_to_json_roundtrips(self) -> None:
        report = ImageReport(
            image_name="app:latest",
            image_id="sha256:xyz",
            total_size_bytes=100,
            layers=[],
            audit_results=[],
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed == report.to_dict()

    def test_audit_result_with_layer_index(self) -> None:
        result = AuditResult(
            rule_id="LARGE_LAYER",
            severity="INFO",
            message="Layer 5 is too large",
            layer_index=5,
        )
        assert result.layer_index == 5

    def test_diff_entry_fields(self) -> None:
        entry = DiffEntry(
            path="/etc/config.txt",
            change_type="modified",
            size_before=100,
            size_after=200,
        )
        assert entry.change_type == "modified"
        assert entry.size_before == 100
        assert entry.size_after == 200
