# dockerlens

[![PyPI version](https://img.shields.io/pypi/v/dockerlens-py)](https://pypi.org/project/dockerlens-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/dockerlens-py)](https://pypi.org/project/dockerlens-py/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Programmatic Docker image layer analysis, auditing, and diffing for Python.**

`dockerlens` is a typed Python library that lets you inspect Docker images from your own code — no CLI scraping, no shell-outs. Think of it as a Pythonic alternative to tools like `dive` or `container-diff`, designed to be imported into your scripts, CI pipelines, and dashboards.

---

## Installation

```bash
pip install dockerlens-py
```

Requires Python 3.9+ and a running Docker daemon (for image inspection, not for tests).

---

## CLI Usage

`dockerlens` now provides a command-line interface for quick analysis:

```bash
# Analyze an image (prints rich tables to terminal)
dockerlens analyze nginx:latest

# Analyze an image directly from Docker Hub without pulling it locally!
dockerlens analyze --remote nginx:latest

# Export analysis as JSON, Markdown, or HTML
dockerlens analyze nginx:latest --format markdown > report.md
dockerlens analyze nginx:latest --format json > report.json

# Compare two images
dockerlens diff nginx:1.24 nginx:latest
```

---

## Quick Start (Python API)

```python
from dockerlens import ImageAnalyzer

# Analyze an image (local)
analyzer = ImageAnalyzer("nginx:latest")

# Analyze an image directly from remote registry (daemonless)
remote_analyzer = ImageAnalyzer("nginx:latest", remote=True)

# Inspect layers
for layer in analyzer.layers():
    print(f"Layer {layer.index}: {layer.size_human:>10}  {layer.command}")

# Run security & best-practice audit
for issue in analyzer.audit():
    print(f"[{issue.severity}] {issue.rule_id}: {issue.message}")

# Compare two images
for change in analyzer.diff("nginx:1.24"):
    print(f"  {change.change_type:>8}  {change.path}")

# Generate a full report as JSON
report = analyzer.report()
print(report.to_json())

# Pretty-print to the terminal with rich
analyzer.print_layers()
analyzer.print_audit()
analyzer.print_diff("nginx:1.24")
```

---

## API Reference

### `ImageAnalyzer(image, docker_client=None, remote=False)`

Main entry point. Pass an image name/tag (e.g. `"nginx:latest"`). If `remote=True`, it will fetch metadata directly from Docker Hub via the HTTP API, requiring no local Docker daemon!

| Method | Returns | Description |
|---|---|---|
| `layers()` | `list[Layer]` | Ordered list of image layers (base → top) |
| `audit()` | `list[AuditResult]` | Best-practice audit findings |
| `diff(other)` | `list[DiffEntry]` | Filesystem differences vs. another image |
| `report()` | `ImageReport` | Combined layers + audit, serializable to JSON |
| `print_layers()` | `None` | Pretty-print layer table to terminal |
| `print_audit()` | `None` | Pretty-print audit results to terminal |
| `print_diff(other)` | `None` | Pretty-print filesystem diff to terminal |

### Data Classes

- **`Layer`** — `index`, `digest`, `size_bytes`, `command`, `created_at`, `size_human` (property)
- **`AuditResult`** — `rule_id`, `severity`, `message`, `layer_index`
- **`DiffEntry`** — `path`, `change_type`, `size_before`, `size_after`
- **`ImageReport`** — `image_name`, `image_id`, `total_size_bytes`, `layers`, `audit_results`, `to_dict()`, `to_json()`

### Exceptions

- **`DockerLensError`** — base exception
- **`DockerNotAvailable`** — Docker daemon unreachable
- **`ImageNotFound`** — image not present locally
- **`RemoteRegistryError`** — network or registry error when fetching via `--remote`

---

## Audit Rules

| Rule ID | Severity | Description |
|---|---|---|
| `NO_USER` | WARNING | Container runs as root — no `USER` instruction found |
| `APT_CACHE_NOT_CLEARED` | WARNING | `apt-get install` without cache cleanup in the same layer |
| `LATEST_TAG` | INFO | Image uses the `:latest` tag (non-reproducible builds) |
| `LARGE_LAYER` | INFO | A single layer exceeds 200 MB |
| `ADD_INSTEAD_OF_COPY` | INFO | `ADD` used instead of `COPY` (implicit tar extraction / URL fetch) |
| `SECRET_PATTERN` | ERROR | Environment variable name matches `PASSWORD`, `SECRET`, `API_KEY`, or `TOKEN` |
| `MANY_LAYERS` | INFO | Image has more than 20 layers |
| `CURL_BASH_PATTERN` | WARNING | `curl` or `wget` piped to `bash`/`sh` |
| `EXPOSED_SSH_PORT` | WARNING | SSH port 22 is exposed |
| `APK_NO_CACHE` | WARNING | `apk add` used without `--no-cache` |
| `PIP_NO_CACHE_DIR` | WARNING | `pip install` used without `--no-cache-dir` |

---

## CI/CD Integration (GitHub Actions)

You can easily integrate `dockerlens` into your CI pipelines to generate Markdown step summaries.

```yaml
jobs:
  analyze-image:
    runs-on: ubuntu-latest
    steps:
      - name: Install dockerlens
        run: pip install dockerlens-py
        
      - name: Analyze Image
        run: dockerlens analyze my-app:latest --format markdown >> $GITHUB_STEP_SUMMARY
```

---

## JSON Output

```python
report = ImageAnalyzer("nginx:latest").report()
print(report.to_json())
```

```json
{
  "image_name": "nginx:latest",
  "image_id": "sha256:abc123...",
  "total_size_bytes": 142000000,
  "layers": [
    {
      "index": 0,
      "digest": "sha256:a3ed...",
      "size_bytes": 80000000,
      "command": "ADD file:abc in /",
      "created_at": "2024-11-14T22:13:20+00:00"
    }
  ],
  "audit_results": [
    {
      "rule_id": "NO_USER",
      "severity": "WARNING",
      "message": "Container runs as root (no USER instruction found)",
      "layer_index": null
    }
  ]
}
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and code style guidelines.

---

## License

MIT — see [LICENSE](LICENSE) for details.
