# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
