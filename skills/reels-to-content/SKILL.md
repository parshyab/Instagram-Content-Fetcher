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

Call `fetch_account` with `account` = the pasted link or handle, `tab: "reels"`, `since: "all"`, `timezone` = the user's IANA timezone.

- Big accounts take several minutes. If the result says `status: "running"`, tell the user once in a short line (e.g. "Fetching @handle's reels — 40 so far"), then keep calling `fetch_account` with the **same arguments** until `status` is `"ready"`. Each call waits about 40 s and continues the same run; it never starts or pays for a second job. Don't wait between calls and don't ask the user.
- If the call itself times out ("did not respond within 60s"), call `status` and then `fetch_account` again with the same arguments; never pass `refresh` or `new_job` to recover.
- `mindcase_notices` (e.g. low balance) → mention them in one line. A run stopped at $0 keeps the reels delivered so far; analyse those and say how many.
- `status: "no_posts"` or a `MINDCASE_HTTP_402` error → tell the user their Mindcase balance needs topping up (https://console.mindcase.co/account?tab=billing).
- Use only the returned numbers. Never estimate. Results are cached for 24 h.
- Optionally, if the profile has a `handle`, also fetch the user's own account (`since` = 6 months ago) to match their voice and avoid repeating their topics. Skip on error.

## 2. Classify pillars

Call `get_posts` (limit 200, page with `offset` while `has_more`) and read every caption. Follow `${CLAUDE_PLUGIN_ROOT}/skills/analyze-instagram-account/references/analysis-framework.md`: define 4–7 pillars, tag every post id with exactly one pillar, then call `pillar_stats` with the full `{post_id: pillar}` map to get counts, shares, median views/engagement and lift vs the account median. For more than 600 reels, classify the most recent 600 and say so.

Focus on what drives **views**: topics, hook styles, series/templates, length, and what the top 10 share that the bottom 5 lack.

## 3. Create content for the user's profile

Default output is a **reel-for-reel remake pack**: for each of the account's top reels by views (15 by default; the user's number if given; "all" = every reel, delivered in batches of 15), write the equivalent reel for the user's profile, following `references/content-pack.md`.

What a remake keeps, matching the original reel closely:
- the same topic and promise (the same tool, problem or result),
- the same hook *type* and structure, the same beat order and approximate length,
- the same format (talking head, screen recording, list, before/after…), CTA type and series role.

What it changes, always:
- **all wording is new**: fresh hook lines, script, on-screen text and caption written for the user's audience. Never copy or translate their caption or lines sentence by sentence, and don't reuse catchphrases, jokes or their persona.
- the user's own angle: their examples, their offer (at most 1 in 4 reels), their `tone`; respect `avoid`.

Why: identical scripts from a same-niche account are recognised by the shared audience and can be reported for copying, so a remake keeps what makes the reel perform and replaces its words. If the user insists on word-for-word copies, explain this in one sentence and keep the remake approach.

Language: scripts, on-screen text, captions and hashtags in the profile `language` and `tone`; keep the "why it works" notes in English unless the user writes in another language. Tie every remake to its source reel (link, views) and to the pattern it reuses. Mindcase returns captions and stats, not the spoken audio, so build each script from the caption, format and metrics, and say so once in Notes.

## 4. Deliver

Create one shareable doc using the session's document tool (Docs artifact type or Claude Docs connector when available; otherwise a Markdown file sent to the user) titled "Reel remakes: @<handle> → @<user handle or \"your page\">". Reply with one line naming the strongest pattern, plus the doc. Offer one next step: the next batch of remakes, or a pack from another account.

## Troubleshooting

- **`mindcase` tools not found** even after ToolSearch → the desktop app isn't running this plugin's connector. Say in plain words: open the Claude desktop app on the computer, make sure this plugin (v0.4.0+) is installed and enabled, and that Python 3 is installed (`python3 --version`; macOS offers to install it on first use). Then ask again.
- **Network error from `fetch_account`** → the computer is offline or a VPN/firewall blocks Mindcase.
- **`401`/`402` errors** → the key is invalid or out of credits: say so plainly.
- Only if the user can't use the desktop app: offer the fallback of allowing `api.mindcase.co` in their Claude network settings so the scripts can run in the cloud workspace (`scripts/fetch_mindcase.py`).
