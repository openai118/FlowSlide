# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [1.0.0] - 2025-08-15

Initial release (consolidated from recent work):

- Fixed critical startup errors in configuration:
  - Rewrote `src/flowslide/core/simple_config.py` to properly initialize attributes (resolved NameError/IndentationError).
  - Ensured DB, security, upload, cache, admin bootstrap, CAPTCHA settings initialize safely.
- AI providers configuration improvements:
  - Added Anthropic `base_url` (default `https://api.anthropic.com`).
  - Added Google Generative AI `base_url` (default `https://generativelanguage.googleapis.com`).
  - Verified UI test routines and runtime providers honor custom base URLs.
- Authentication and UX updates:
  - `/home` kept public and consistent after login; navbar reflects auth state.
  - Post-login and post-register redirects now land on `/home` instead of `/dashboard`.
- Repository hygiene and docs:
  - Added `docs/_site/` to `.gitignore` to avoid tracking generated site files.
  - Cleaned temp artifacts and removed local SQLite `data/flowslide.db` from version control.
- Packaging and metadata:
  - Project metadata points to `openai118/FlowSlide` repository and homepage.

### Notes
- Default admin creation and SQLite startup validated.
- Ready for deployment; see `DEPLOYMENT_GUIDE.md` and Docker assets.

[1.0.0]: https://github.com/openai118/FlowSlide/releases/tag/v1.0.0
