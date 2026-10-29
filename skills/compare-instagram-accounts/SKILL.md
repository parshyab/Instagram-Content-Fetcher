---
name: compare-instagram-accounts
description: Compares the content strategies of two or more Instagram accounts side by side. Use when the user says "compare @a and @b", "benchmark these competitors on Instagram", "how does my page stack up against these accounts", "competitor content analysis", or lists several Instagram handles to analyse together.
---

# Compare Instagram accounts

Benchmark 2–6 Instagram accounts on content pillars, formats, hooks, engagement and cadence, and find the opportunities the user can act on.

## Steps

1. **Collect handles.** Confirm the list (max 6; ask which to drop if more). If the user includes their own account, mark it as "you" and frame findings relative to it.
2. **Fetch and compute per account.** For each handle, follow steps 1–2 of the `analyze-instagram-account` skill (same data-source order and scripts; with Mindcase, use the same `--tab` and `--since` for every account). Use the same `--limit` and time window for every account so the comparison is fair; if one account has far fewer posts, note it.
3. **Classify pillars with a shared taxonomy.** Read captions across all accounts first, then define one set of 5–8 shared pillar categories that covers every account. Tag every post into it, save `<handle>_pillars.json` per account, and compute pillar share and median engagement per account in code.
4. **Build the comparison in code.** Write one Python snippet that loads every `_metrics.json` and pillar file and produces the snapshot table, pillar-share table, and format-mix table. Use engagement **rate** when follower counts differ by more than 2×.
5. **Find the gaps.** Identify: pillars one account wins with that others ignore; formats with high engagement but low usage; cadence differences; hook styles unique to the top performer; white-space topics no one covers well.
6. **Write the report** as a shareable doc, following the "Comparison report structure" in `${CLAUDE_PLUGIN_ROOT}/skills/analyze-instagram-account/references/analysis-framework.md`. Lead with the one-paragraph verdict; end with "Opportunities for you".

## Rules

- Every number comes from computed data, never estimated.
- Quote hooks as short excerpts only and link the post.
- State caveats once in the Method section (public data only, current-follower ER, sample sizes).

## Finishing

Reply with the single biggest opportunity in one line plus the report. Offer one next step, such as a 4-week content plan built from the opportunities.
