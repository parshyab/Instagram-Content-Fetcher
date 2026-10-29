---
name: reels-to-content
description: The default flow when the user pastes an Instagram account link or @handle. Fetches all of that account's reels, analyses what works, and writes ready-to-film reel content for the user's own profile. Use when the user shares an instagram.com profile URL or a handle with no other instruction, or says "create content like @handle", "turn their reels into ideas for my page", "make reels for me inspired by this account", or "what should I post based on this creator".
---

# Reels → content for the user's profile

Goal: one pasted account in, a content pack for the user's own page out. Run the whole flow without stopping unless setup is missing.

## How data is fetched (read once)

Mindcase is called by this plugin's **`mindcase` MCP tools** (`status`, `save_profile`, `fetch_account`, `get_posts`, `pillar_stats`, `export_posts`). They run on the user's own computer through the Claude desktop app and use its normal internet, so they work even though the cloud workspace and the device shell block `api.mindcase.co`. Always use these tools. Find them with ToolSearch ("mindcase fetch_account") if they are not loaded.

Do **not** run `fetch_mindcase.py` with Bash or the device shell, and do not tell the user to change allowlists or run Terminal commands, unless the MCP tools are genuinely unavailable (see Troubleshooting).

## 0. Check setup (silent)

Call `status`.
- `mindcase_key: false` → the built-in key is missing from the installed plugin: follow the `setup` skill.
- `profile_complete: false` → ask once for the user's niche, audience and language (plus handle, tone, goals if easy), then call `save_profile`. Never ask again once saved.
- Otherwise go straight on. Never mention the key.

## 1. Fetch and measure all reels

Call `fetch_account` with `account` = the pasted link or handle, `tab: "reels"`, `since: "all"`, `timezone` = the user's IANA timezone. It returns computed metrics (format mix, cadence, best times, engagement, views, hooks, CTAs, hashtags, top and bottom posts). Use only these numbers. Never estimate.

- Results are cached for 24 h; pass `refresh: true` only if the user asks for fresh data.
- Use a narrower `since` only if the user asks.
- Optionally, if the profile has a `handle`, also call `fetch_account` for the user's own account with `since` = 6 months ago, to match their voice and avoid repeating their topics. Skip on error.

## 2. Classify pillars

Call `get_posts` (limit 200, page with `offset` while `has_more`) and read every caption. Follow `${CLAUDE_PLUGIN_ROOT}/skills/analyze-instagram-account/references/analysis-framework.md`: define 4–7 pillars, tag every post id with exactly one pillar, then call `pillar_stats` with the full `{post_id: pillar}` map to get counts, shares, median views/engagement and lift vs the account median. For more than 600 reels, classify the most recent 600 and say so.

Focus on what drives **views**: topics, hook styles, series/templates, length, and what the top 10 share that the bottom 5 lack.

## 3. Create content for the user's profile

Write the content pack following `references/content-pack.md`:
- **Adapt patterns, never copy.** Borrow the mechanics that work (hook structure, pacing, series format, CTA style, topic angle) and apply them to the user's niche and audience. Don't reuse their scripts, captions, jokes or catchphrases, or imitate their persona.
- Write scripts, on-screen text, captions and hashtags in the profile `language` and `tone`; keep the "why it works" notes in English unless the user writes in another language.
- Tie each idea to a specific finding with its number.
- If the pasted account is in another niche, translate its mechanics and say so in one line.
- Respect `avoid`; weave in `offer` on at most 1 in 4 reels.

## 4. Deliver

Create one shareable doc using the session's document tool (Docs artifact type or Claude Docs connector when available; otherwise a Markdown file sent to the user) titled "Content pack: inspired by @<handle>". Reply with one line naming the strongest borrowed pattern, plus the doc. Offer one next step: more reels in a winning series, or a pack from another account.

## Troubleshooting

- **`mindcase` tools not found** even after ToolSearch → the desktop app isn't running this plugin's connector. Say in plain words: open the Claude desktop app on the computer, make sure this plugin (v0.4.0+) is installed and enabled, and that Python 3 is installed (`python3 --version`; macOS offers to install it on first use). Then ask again.
- **Network error from `fetch_account`** → the computer is offline or a VPN/firewall blocks Mindcase.
- **`401`/`402` errors** → the key is invalid or out of credits: say so plainly.
- Only if the user can't use the desktop app: offer the fallback of allowing `api.mindcase.co` in their Claude network settings so the scripts can run in the cloud workspace (`scripts/fetch_mindcase.py`).
