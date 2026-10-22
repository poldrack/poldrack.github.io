# The site is rendered and deployed by GitHub Actions on push to main.
# These targets are for local work only.

.PHONY: preview render test import-blogger

preview:
	uv run quarto preview

render:
	uv run quarto render .
	uv run python fix_mastodon_link.py

test:
	uv run pytest

import-blogger:
	uv run python -m poldrack_github_io.blogger_post blog/posts
