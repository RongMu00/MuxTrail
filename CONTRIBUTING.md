# Contributing

Use Python 3.11+, keep channel adapters provider-agnostic, and preserve the normalized Gateway
path. Add focused tests for every behavior change and run `pytest -q`, `ruff check`, `mypy`, and the
frontend production build before opening a change. Never commit credentials, `.env`, runtime state,
dependency directories, caches, build output, or logs.

Document whether new functionality is implemented, optional, experimental, or planned. User-facing
copy and examples should be clear English and avoid unsupported reliability claims.
