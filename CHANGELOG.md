# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-24

### Added

- **Daemonless Remote Registry Scanning**: Added the `--remote` flag to `dockerlens analyze`. You can now scan images directly from Docker Hub without needing a local Docker daemon or pulling the image!
- Programmatic Python API now supports `ImageAnalyzer(..., remote=True)` to fetch layer metadata via the registry API (`urllib.request`), leaving no footprint on the host machine.
- **CLI wrapper**: Added `dockerlens` command-line tool with `analyze` and `diff` commands.
- **Export Formats**: Added `to_markdown()` and `to_html()` methods to `ImageReport`.
- **New Audit Rules**:
  - `CURL_BASH_PATTERN` — warns when `curl ... | bash` is used.
  - `EXPOSED_SSH_PORT` — warns when port 22 is exposed.
  - `APK_NO_CACHE` — warns when `apk add` is used without `--no-cache`.
  - `PIP_NO_CACHE_DIR` — warns when `pip install` is used without `--no-cache-dir`.

## [0.1.0] - 2026-05-24

### Added

- **Layer analysis**: Inspect every layer of a Docker image, including size, digest, command, and creation timestamp.
- **Security & best-practice auditing**: 7 built-in audit rules:
  - `NO_USER` — warn when container runs as root
  - `APT_CACHE_NOT_CLEARED` — warn when apt cache is not cleaned after install
  - `LATEST_TAG` — info when using the `:latest` tag
  - `LARGE_LAYER` — info when a layer exceeds 200 MB
  - `ADD_INSTEAD_OF_COPY` — info when `ADD` is used instead of `COPY`
  - `SECRET_PATTERN` — error when environment variables suggest hardcoded secrets
  - `MANY_LAYERS` — info when image has more than 20 layers
- **Image diffing**: Compare two Docker images at the filesystem level with whiteout support.
- **Rich terminal output**: Pretty-printed tables for layers, audit results, and diffs.
- **JSON serialization**: `ImageReport.to_json()` for machine-readable output.
- **Typed dataclasses**: `Layer`, `AuditResult`, `DiffEntry`, `ImageReport`.
- **Custom exceptions**: `DockerLensError`, `DockerNotAvailable`, `ImageNotFound`.
