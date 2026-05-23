"""Tests for dockerlens.audit.AuditEngine."""

from __future__ import annotations

from dockerlens.audit import AuditEngine


def _make_engine(
    history: list[dict],  # type: ignore[type-arg]
    config_user: str = "",
    repo_tags: list[str] | None = None,
) -> AuditEngine:
    """Helper to construct an AuditEngine with minimal image data."""
    if repo_tags is None:
        repo_tags = ["myapp:v1.0"]
    image_data: dict = {  # type: ignore[type-arg]
        "RepoTags": repo_tags,
        "Config": {
            "User": config_user,
            "Env": ["PATH=/usr/local/bin"],
        },
    }
    return AuditEngine(image_data, history)


class TestNoUser:
    """Tests for the NO_USER rule."""

    def test_fires_when_no_user(self) -> None:
        history = [
            {"CreatedBy": "/bin/sh -c echo hello", "Size": 100, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_no_user()
        assert len(results) == 1
        assert results[0].rule_id == "NO_USER"
        assert results[0].severity == "WARNING"

    def test_does_not_fire_when_config_user_set(self) -> None:
        history = [
            {"CreatedBy": "/bin/sh -c echo hello", "Size": 100, "Created": 0},
        ]
        engine = _make_engine(history, config_user="appuser")
        results = engine._check_no_user()
        assert len(results) == 0

    def test_does_not_fire_when_user_in_history(self) -> None:
        history = [
            {"CreatedBy": "/bin/sh -c #(nop)  USER appuser", "Size": 0, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_no_user()
        assert len(results) == 0


class TestAptCache:
    """Tests for the APT_CACHE_NOT_CLEARED rule."""

    def test_fires_when_no_cleanup(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c apt-get install -y curl",
                "Size": 40_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_apt_cache()
        assert len(results) == 1
        assert results[0].rule_id == "APT_CACHE_NOT_CLEARED"

    def test_does_not_fire_when_cleaned(self) -> None:
        history = [
            {
                "CreatedBy": (
                    "/bin/sh -c apt-get install -y curl"
                    " && rm -rf /var/lib/apt/lists/*"
                ),
                "Size": 40_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_apt_cache()
        assert len(results) == 0

    def test_does_not_fire_when_apt_get_clean(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c apt-get install -y curl && apt-get clean",
                "Size": 40_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_apt_cache()
        assert len(results) == 0

    def test_does_not_fire_without_install(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c apt-get update",
                "Size": 10_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_apt_cache()
        assert len(results) == 0


class TestLatestTag:
    """Tests for the LATEST_TAG rule."""

    def test_fires_on_latest(self) -> None:
        history = [
            {"CreatedBy": "CMD", "Size": 0, "Created": 0},
        ]
        engine = _make_engine(history, repo_tags=["nginx:latest"])
        results = engine._check_latest_tag()
        assert len(results) == 1
        assert results[0].rule_id == "LATEST_TAG"
        assert results[0].severity == "INFO"

    def test_does_not_fire_on_specific_tag(self) -> None:
        history = [
            {"CreatedBy": "CMD", "Size": 0, "Created": 0},
        ]
        engine = _make_engine(history, repo_tags=["nginx:1.25.3"])
        results = engine._check_latest_tag()
        assert len(results) == 0


class TestLargeLayer:
    """Tests for the LARGE_LAYER rule."""

    def test_fires_on_large_layer(self) -> None:
        large_size = 300 * 1024 * 1024  # 300 MB
        history = [
            {"CreatedBy": "COPY . /app", "Size": large_size, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_large_layers()
        assert len(results) == 1
        assert results[0].rule_id == "LARGE_LAYER"

    def test_does_not_fire_on_small_layer(self) -> None:
        history = [
            {"CreatedBy": "COPY . /app", "Size": 10_000_000, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_large_layers()
        assert len(results) == 0


class TestAddInstruction:
    """Tests for the ADD_INSTEAD_OF_COPY rule."""

    def test_fires_on_add(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop) ADD file:abc123 in /",
                "Size": 80_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_add_instruction()
        assert len(results) == 1
        assert results[0].rule_id == "ADD_INSTEAD_OF_COPY"

    def test_does_not_fire_on_copy(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop) COPY file:abc123 in /app",
                "Size": 5_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_add_instruction()
        assert len(results) == 0

    def test_does_not_fire_on_run_with_add_word(self) -> None:
        # A RUN command that happens to contain the word "add" should not trigger
        history = [
            {"CreatedBy": "/bin/sh -c useradd appuser", "Size": 1000, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_add_instruction()
        assert len(results) == 0


class TestSecretPattern:
    """Tests for the SECRET_PATTERN rule."""

    def test_fires_on_password(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop)  ENV DB_PASSWORD=hunter2",
                "Size": 0,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_secret_patterns()
        assert len(results) == 1
        assert results[0].rule_id == "SECRET_PATTERN"
        assert results[0].severity == "ERROR"

    def test_fires_on_api_key(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop)  ENV MY_API_KEY=abc123",
                "Size": 0,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_secret_patterns()
        assert len(results) == 1

    def test_fires_on_token(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop)  ENV AUTH_TOKEN=xyz",
                "Size": 0,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_secret_patterns()
        assert len(results) == 1

    def test_does_not_fire_on_safe_env(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c #(nop)  ENV PATH=/usr/local/bin",
                "Size": 0,
                "Created": 0,
            },
        ]
        engine = _make_engine(history)
        results = engine._check_secret_patterns()
        assert len(results) == 0

    def test_does_not_fire_on_non_env(self) -> None:
        history = [
            {"CreatedBy": "/bin/sh -c echo password", "Size": 0, "Created": 0},
        ]
        engine = _make_engine(history)
        results = engine._check_secret_patterns()
        assert len(results) == 0


class TestManyLayers:
    """Tests for the MANY_LAYERS rule."""

    def test_fires_over_threshold(self) -> None:
        history = [
            {"CreatedBy": f"RUN echo {i}", "Size": 100, "Created": 0} for i in range(25)
        ]
        engine = _make_engine(history)
        results = engine._check_many_layers()
        assert len(results) == 1
        assert results[0].rule_id == "MANY_LAYERS"

    def test_does_not_fire_under_threshold(self) -> None:
        history = [
            {"CreatedBy": f"RUN echo {i}", "Size": 100, "Created": 0} for i in range(5)
        ]
        engine = _make_engine(history)
        results = engine._check_many_layers()
        assert len(results) == 0


class TestRunAll:
    """Integration test for AuditEngine.run_all()."""

    def test_run_all_collects_multiple_findings(self) -> None:
        history = [
            {
                "CreatedBy": "/bin/sh -c apt-get install -y curl",
                "Size": 40_000_000,
                "Created": 0,
            },
        ]
        engine = _make_engine(history, repo_tags=["app:latest"])
        results = engine.run_all()
        rule_ids = {r.rule_id for r in results}
        # Should at least find NO_USER, APT_CACHE_NOT_CLEARED, LATEST_TAG
        assert "NO_USER" in rule_ids
        assert "APT_CACHE_NOT_CLEARED" in rule_ids
        assert "LATEST_TAG" in rule_ids
