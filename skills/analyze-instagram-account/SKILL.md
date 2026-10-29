---
name: analyze-instagram-account
description: Produces an analysis report (no content creation) of another Instagram account's posts and reels, explaining what content it creates and what works. Use when the user explicitly asks for analysis, e.g. "analyse @handle on Instagram", "what kind of content does this account post", "break down this creator's Instagram", "audit this competitor's posts", "what are their content pillars", or shares an export of someone's posts. A bare pasted profile link goes to the reels-to-content skill instead.
---

# Analyse an Instagram account

Produce an evidence-based breakdown of one Instagram account's content: pillars, formats, hooks, captions, engagement and cadence, ending in a shareable report doc with clear takeaways.

## 1. Get the data

Pick the source in this order:

1. **Supplied data first.** If the user attached or pasted post data (CSV, JSON, a table, or screenshots), use it. For screenshots, transcribe each visible post into rows (caption, format, likes, comments, views, date) in a CSV in the working directory before continuing.
2. **Mindcase via the plugin's `mindcase` MCP tools (default for any public account).** These run on the user's computer with its normal internet, so they work even though the cloud workspace blocks `api.mindcase.co`. Load them with ToolSearch ("mindcase fetch_account") if needed.
   - Call `fetch_account` (`account`, `tab`: `posts,reels` for a full analysis, `reels` or `posts` if asked; `since`: the user's date, else `all`; `timezone`). It returns the computed metrics; skip step 2 below.
   - For step 3, read captions with `get_posts` (page with `offset`) and compute pillar stats with `pillar_stats` instead of local scripts.
   - `export_posts` writes the raw posts as JSON/CSV to the user's Documents folder if they want the data.
   - If the tools aren't available, follow Troubleshooting in the `reels-to-content` skill. Never echo the key.
3. **Graph API.** Otherwise, if `IG_ACCESS_TOKEN` and `IG_USER_ID` are set, run:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_ig.py api <username> --limit 200 --out <username>_posts.json
   ```
   Default to the latest 200 posts; use the user's number if they give one ("all posts" → `--limit` equal to the account's media count, capped at 1000 unless they insist).
4. **None available.** Explain the options in plain language: save a Mindcase key (the `setup` skill), connect the Graph API (walk them through `references/graph-api-setup.md`), or export/paste the posts. Do not scrape Instagram pages yourself or log in as the user to collect posts.

For supplied files, normalise them:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_ig.py file <path> --username <name> [--followers N] --out <name>_posts.json
```
Ask for the follower count if it is missing and engagement rate matters; otherwise proceed and note that rates were not computed.

If the API reports the account is not a Business/Creator account, or is age-gated, say so in one line and offer the export route.

## 2. Compute the metrics (file and Graph API sources only)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze.py <name>_posts.json --tz <user's IANA timezone> 
```
Read the resulting `_metrics.json`. All numbers in the report come from this file or from code run on the posts file — never estimate figures in prose.

## 3. Classify content pillars (Claude's judgement)

Using `posts_for_classification`, follow the method in `references/analysis-framework.md`:
- Read every caption (and hook) and define 4–7 mutually exclusive pillars named in the account's own terms (e.g. "AI tool tutorials", "founder diary"), plus "Other".
- Write a one-line definition per pillar, then tag every post with exactly one pillar.
- Save the tags to `<name>_pillars.json` (`{post_id: pillar}`) and run a short Python snippet joining them with the posts file to compute count, share and median engagement per pillar, and pillar × format. Do not eyeball these numbers.
- For accounts with more than 300 posts, classify the most recent 300 and say so.

Also qualitatively note: tone of voice, language(s) used, recurring series or templates, on-screen/visual style visible from captions, collaborations (top mentions), and how they use CTAs.

## 4. Write the report

Create a shareable report doc using the session's document tool (the Docs artifact type or Claude Docs connector when available; otherwise a Markdown file sent to the user). Follow the report structure in `references/analysis-framework.md`. Keep it scannable: short sections, tables for numbers, 3–5 quoted top hooks (short excerpts only, with links to the posts).

Lead with the answer: a 3–4 sentence summary of what this account makes and what drives its best results. End with "What to borrow" — 5–7 concrete, actionable ideas for the user's own content, each tied to a finding.

## 5. Caveats to state (only those that apply)

- Only public data is available from either API: no reach, saves, shares or story data.
- Mindcase is a third-party data provider: note the source and the `--since` window in the Method section.
- Hidden like counts appear as missing; reels whose owner disabled downloads may lack media URLs (does not affect analysis).
- Engagement rate = (likes + comments) ÷ current followers, so older posts are judged against today's follower count.
- Small samples (<20 posts) → describe patterns, avoid strong conclusions.

## Finishing

Reply with one line on the account's defining pattern plus the report. Offer one next step: comparing against other accounts (the compare-instagram-accounts skill) or turning "What to borrow" into a content calendar.
