---
name: reels-to-content
description: The default flow when the user pastes an Instagram account link or @handle. Fetches all of that account's reels, analyses what works, and writes ready-to-film reel content for the user's own profile. Use when the user shares an instagram.com profile URL or a handle with no other instruction, or says "create content like @handle", "turn their reels into ideas for my page", "make reels for me inspired by this account", or "what should I post based on this creator".
---

# Reels → content for the user's profile

Goal: one pasted account in, a content pack for the user's own page out. Run the whole flow without stopping unless setup is missing.

## 0. Check setup (silent)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py status
```
- `mindcase_key: false` → follow the `setup` skill to get and save the key, then continue.
- `profile_complete: false` → ask once for the user's niche, audience and language (and handle, tone, goals if easy), save them with the `setup` skill, then continue. Never ask again once saved.
- Both present → go straight on. Do not mention the key.

## 1. Fetch all reels of the pasted account

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_mindcase.py "<pasted link or handle>" --tab reels --since all --out <handle>_posts.json
```
- "All reels" is the default. Use a narrower `--since` only if the user asks, or if the account has more than ~500 reels and the user agrees after you mention the size.
- If the script prints `NO_MINDCASE_KEY`, run step 0's key setup and retry once.
- Empty fields warning → inspect `<handle>_mindcase_raw.json`, map fields in a short snippet, continue.

Optionally, if the saved profile has a `handle` and this session has not done so yet, also fetch the user's own recent reels (`--tab reels --since <6 months ago> --out me_posts.json`) to match their voice and avoid repeating their existing topics. Skip if it fails; it is a nice-to-have.

## 2. Analyse the reels

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py <handle>_posts.json --tz <user's IANA timezone>
```
Then follow `${CLAUDE_PLUGIN_ROOT}/skills/analyze-instagram-account/references/analysis-framework.md` for pillars (tag every reel, compute per-pillar stats in code), hooks, captions, views, cadence, and top vs bottom reels. Pay most attention to:
- Which topics and hook styles get the most **views** (reels are distributed by views, not likes).
- Recurring series, templates, and on-screen formats.
- What the top 10 reels share that the bottom 5 lack.

Every number comes from computed data. Never estimate.

## 3. Create content for the user's profile

Read the saved profile and write a content pack following `references/content-pack.md`. Rules:
- **Adapt patterns, never copy.** Borrow the *mechanics* that work (hook structure, pacing, series format, CTA style, topic angle) and apply them to the user's niche and audience. Do not reuse their scripts, captions, jokes or distinctive catchphrases, and do not imitate their persona.
- Write scripts, on-screen text, captions and hashtags in the profile `language`, in the profile `tone`. Keep the reasoning notes (the "why it works" lines) in English unless the user writes in another language.
- Tie each idea to a specific finding ("Their numbered-list hooks get 2.1× median views → …").
- If the pasted account is in a different niche, translate the winning mechanics across and say so in one line.
- Respect `avoid`; weave in `offer` on at most 1 in 4 reels.

## 4. Deliver

Create one shareable doc using the session's document tool (Docs artifact type or Claude Docs connector when available; otherwise a Markdown file sent to the user) titled "Content pack: inspired by @<handle>". Reply with one line naming the single strongest pattern you borrowed, plus the doc. Offer one next step: more reels in a winning series, or a pack from another account.
