# Backend key

Put the Mindcase API key in `backend/mindcase.key` (one line, `mk_live_...`).
The plugin uses it automatically, so users never have to paste a key.

This file is git-ignored on purpose: the GitHub repo is public, and a key
committed there can be found and used by anyone. It is included only in the
packaged `.plugin` file you install locally — don't share that file publicly.

Lookup order: `MINDCASE_API_KEY` env var → user's saved settings
(`~/.config/instagram-content-analyser/config.json`) → `backend/mindcase.key`.
