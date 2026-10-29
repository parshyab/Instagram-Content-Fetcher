---
name: setup
description: Saves the Mindcase API key and the user's own Instagram creator profile so they never have to paste them again. Use when the user pastes a Mindcase key (mk_live_... or mk_test_...), says "set up the analyser", "save my Mindcase key", "update my profile/niche/language", "change my API key", or "show my settings", and whenever another skill in this plugin reports NO_MINDCASE_KEY or an incomplete profile.
---

# Set up Instagram Content Analyser

Settings live in a private file on the user's machine (`~/.config/instagram-content-analyser/config.json`, owner-only permissions), outside the plugin and any git repo. Manage it only through the script:

```bash
CFG="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py"
$CFG status          # what's saved (JSON; key shown only as true/false)
$CFG show            # settings with the key masked
```

## Save the Mindcase key

When the user pastes a key, save it immediately; do not ask for confirmation:
```bash
printf '%s' 'mk_live_...' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py set-key -
```
- Never repeat the full key in chat, in files you write, in memory, or in commit messages. Refer to it only by the masked form the script prints.
- Never write the key into the plugin folder, a `.env` inside a repo, or any file that could be committed.
- Suggest once that they rotate the key in Mindcase if it was pasted somewhere public.
- To replace it, run `set-key` again; to remove it, `clear-key`.

## Save the creator profile

The profile is the user's own Instagram page that content gets written for. Required: `niche`, `audience`, `language`. Recommended: `handle`, `tone`, `goals`. Optional: `offer` (product/service to promote), `avoid` (topics or styles to steer clear of), `formats` (what they can realistically film).

Ask for missing required fields in one short question (AskUserQuestion when available, otherwise plain text). Accept free-form answers and map them yourself. Then save:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py set-profile handle=yourpage "niche=AI tools for beginners" "audience=students and working professionals new to AI" language=Assamese "tone=friendly, simple, energetic" "goals=grow followers, sell course"
```
Quote each `key=value` pair. Updating one field leaves the others unchanged.

## Finishing

Confirm in one line what is saved (masked key, profile summary), then continue with whatever the user originally asked for.
