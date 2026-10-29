# Graph API setup (Business Discovery)

Walk the user through this in plain language, one step at a time.

## What it can and can't see

- Works only on **public Instagram Business or Creator accounts** that are not age-gated. Personal accounts cannot be analysed this way.
- Returns account basics (followers, media count, bio) and, per post: caption, media type (image / video / carousel), product type (feed / reels), likes, comments, views (where available), timestamp, permalink, carousel children.
- Does not return reach, saves, shares, stories or comment text of other accounts.
- Rate limit is per user per hour; the fetch script pages 50 posts per call and pauses between pages.

## Requirements

1. The user's **own** Instagram account must be a Business or Creator account, linked to a Facebook Page.
2. A Meta developer app using **Instagram API with Facebook Login** (Business Discovery is not available with Instagram Login).
3. Permissions on the token: `instagram_basic` and `pages_show_list` (plus `pages_read_engagement`, `ads_management` or `business_management` if the Page role came through Business Manager). `instagram_manage_insights` is not needed.
4. A long-lived user access token (about 60 days; refresh before expiry).

## Steps

1. Create an app at developers.facebook.com → add the Instagram product (Facebook Login flavour).
2. In Graph API Explorer, select the app, request the permissions above, and generate a user token. Exchange it for a long-lived token.
3. Find the IG user ID: `GET /me/accounts?fields=instagram_business_account{id,username}` — use `instagram_business_account.id`.
4. Set environment variables where Claude runs:
   - `IG_ACCESS_TOKEN` = the long-lived token
   - `IG_USER_ID` = the IG user ID from step 3
   - optional `IG_GRAPH_VERSION` (defaults to `v25.0`)
5. Test: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_ig.py api instagram --limit 5`.

Never print, store in memory, or paste the token back into chat. If the user pastes a token in chat, use it only via an environment variable for this session and suggest they rotate it afterwards.

## Common errors

| Message | Meaning |
|---|---|
| "Invalid user id" / "Cannot query users by their username" | Target is not a Business/Creator account, or the username is wrong |
| code 190 | Token expired or invalid — regenerate |
| code 10 / 200 | Missing permission on the token |
| code 4 / 32 / 613 | Rate limited — wait and retry with a smaller `--limit` |
| Network error | The environment blocks graph.facebook.com; run the plugin from the desktop app or use exported data |
