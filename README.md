# Instagram Content Analyser by Parshya

Analyse what other Instagram accounts post and what works for them — content pillars, formats, hooks, captions, engagement and posting cadence — and compare several accounts side by side. Results come back as a shareable report doc.

## Skills

| Skill | Use it for |
|---|---|
| `analyze-instagram-account` | Deep breakdown of one account: "analyse @handle", "what content does this account make?" |
| `compare-instagram-accounts` | Benchmark 2–6 accounts: "compare @a, @b and @c" |

## Data sources

1. **Mindcase API** (default) — fetches the profile and posts/reels of any public account, personal or business, via the Mindcase `profiles` and `posts` agents. Needs a Mindcase key (`mk_live_...`).
2. **Instagram Graph API (Business Discovery)** — official, works on public Business/Creator accounts. Needs your own IG Business/Creator account linked to a Facebook Page and a token. Setup: `skills/analyze-instagram-account/references/graph-api-setup.md`.
3. **Exported or pasted data** — CSV/JSON exports from any analytics tool, a pasted table, or screenshots. Recognised columns: `caption`, `type`/`media_type`, `likes`, `comments`, `views`, `date`/`timestamp`, `url`/`permalink`, `slides`.

The plugin itself does not scrape Instagram pages; Mindcase is a third-party provider you choose to use with your own key.

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `MINDCASE_API_KEY` | for Mindcase | Your `mk_live_...` key |
| `MINDCASE_BASE_URL` | no | Defaults to `https://api.mindcase.co/api/v1` |
| `IG_ACCESS_TOKEN` | for Graph API | Long-lived user token, Instagram API with Facebook Login |
| `IG_USER_ID` | for Graph API | Your own IG Business/Creator user ID |
| `IG_GRAPH_VERSION` | no | Defaults to `v25.0` |

## Scripts

- `scripts/fetch_mindcase.py` — fetches profile + posts/reels from Mindcase for any handle or profile URL (`--tab posts,reels`, `--since YYYY-MM-DD`) and saves the raw response for debugging.
- `scripts/fetch_ig.py` — fetches posts via the API (paged) or normalises a CSV/JSON file.
- `scripts/analyze.py` — computes format mix, cadence, timing, engagement by format, caption/hook/CTA/hashtag stats and top posts. Pillar classification is done by Claude on top of this output.

Requires Python 3.9+ with only the standard library.

## What's analysed

- **Content pillars** — topic + intent clusters, share and performance of each
- **Formats & hooks** — Reels vs carousels vs images, carousel length, first-line hook patterns, CTAs, hashtags
- **Engagement & cadence** — engagement and engagement rate, best days/times, posting consistency, trend
- **Competitor comparison** — shared pillar taxonomy, gaps and white space

## Limits

Public data only: no reach, saves, shares or stories for other accounts. Engagement rate uses today's follower count. Personal accounts need Mindcase or exported data; the Graph API only covers Business/Creator accounts. Mindcase usage consumes your Mindcase credits.
