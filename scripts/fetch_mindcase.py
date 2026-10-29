#!/usr/bin/env python3
"""Fetch any public Instagram account's profile and posts/reels through the
Mindcase agents API, and normalise them to the plugin's posts JSON format.

Usage:
  fetch_mindcase.py <handle|@handle|profile URL> [--tab reels|posts|posts,reels]
                    [--since YYYY-MM-DD] [--out posts.json] [--no-profile]

Key: read from MINDCASE_API_KEY, else the saved settings file (see config.py)
Env:
  MINDCASE_API_KEY   optional override
  MINDCASE_BASE_URL  Optional, defaults to https://api.mindcase.co/api/v1

Writes <handle>_posts.json ({"account": {...}, "posts": [...]}) plus the raw
API responses as <handle>_mindcase_raw.json for debugging field mappings.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import mindcase_key  # noqa: E402
from datetime import date, timedelta

BASE = os.environ.get("MINDCASE_BASE_URL", "https://api.mindcase.co/api/v1").rstrip("/")


def handle_of(s):
    s = s.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", s)
    return (m.group(1) if m else s).lstrip("@").strip("/")


def run_agent(agent, params, key):
    url = f"{BASE}/agents/instagram/{agent}/run?wait=true"
    req = urllib.request.Request(
        url, data=json.dumps({"params": params}).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            hint = {401: "API key missing or invalid", 402: "out of Mindcase credits",
                    403: "key not allowed to use this agent"}.get(e.code, "")
            sys.exit(f"Mindcase {agent} error {e.code} {hint}: {body}")
        except urllib.error.URLError as e:
            sys.exit(f"Network error reaching Mindcase: {e.reason}. "
                     "Run from the Claude desktop app or a machine with internet access.")


def find_records(obj, want):
    """Return the first list of dicts that contains any of the `want` keys."""
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        if any(want & set(x) for x in obj):
            return obj
    if isinstance(obj, dict):
        for k in ("data", "results", "items", "output", "result", "records", "rows"):
            if k in obj:
                r = find_records(obj[k], want)
                if r is not None:
                    return r
        for v in obj.values():
            r = find_records(v, want)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_records(v, want)
            if r is not None:
                return r
    return None


def pick(d, *names):
    for n in names:
        cur = d
        for part in n.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


def num(v):
    if isinstance(v, bool):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def norm_ts(v):
    if isinstance(v, (int, float)) and v > 1e9:  # unix seconds/ms
        from datetime import datetime, timezone
        return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, timezone.utc).isoformat()
    return v


def norm_post(p, i):
    t = str(pick(p, "type", "media_type", "mediaType", "__typename") or "").lower()
    product = str(pick(p, "productType", "product_type", "media_product_type") or "").lower()
    children = pick(p, "childPosts", "children", "carousel_media", "sidecar", "images")
    is_reel = "reel" in t or product in ("clips", "reels") or "clip" in t
    if is_reel:
        mt, pt = "VIDEO", "REELS"
    elif "sidecar" in t or "carousel" in t or (isinstance(children, list) and len(children) > 1):
        mt, pt = "CAROUSEL_ALBUM", "FEED"
    elif "video" in t:
        mt, pt = "VIDEO", "FEED"
    else:
        mt, pt = "IMAGE", "FEED"
    cap = pick(p, "caption", "caption.text", "text", "description", "edge_media_to_caption.edges")
    if isinstance(cap, list):
        cap = " ".join(str(pick(c, "node.text") or "") for c in cap)
    url = pick(p, "url", "permalink", "postUrl", "link")
    code = pick(p, "shortCode", "shortcode", "code")
    if not url and code:
        url = f"https://www.instagram.com/{'reel' if is_reel else 'p'}/{code}/"
    likes = num(pick(p, "likesCount", "likes", "like_count", "likeCount", "edge_liked_by.count"))
    if likes is not None and likes < 0:  # hidden likes are often returned as -1
        likes = None
    return {
        "id": str(pick(p, "id", "pk", "shortCode", "shortcode") or i),
        "caption": cap if isinstance(cap, str) else None,
        "media_type": mt, "media_product_type": pt,
        "like_count": likes,
        "comments_count": num(pick(p, "commentsCount", "comments", "comment_count", "comments_count")),
        "view_count": num(pick(p, "videoPlayCount", "playCount", "plays", "videoViewCount",
                               "views", "view_count", "play_count")),
        "timestamp": norm_ts(pick(p, "timestamp", "takenAt", "taken_at", "date", "createdAt", "postedAt")),
        "permalink": url,
        "children_count": len(children) if isinstance(children, list) else None,
        "duration_sec": pick(p, "videoDuration", "video_duration", "duration"),
        "music": pick(p, "musicInfo.song_name", "musicInfo.title", "music.title"),
        "is_pinned": pick(p, "isPinned", "is_pinned"),
        "collaborators": pick(p, "coauthorProducers", "collaborators"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--tab", default="reels", help="reels, posts, or both comma-separated (Mindcase tab param)")
    ap.add_argument("--since", default=(date.today() - timedelta(days=730)).isoformat(),
                    help="onlyPostsNewerThan, YYYY-MM-DD (default: 2 years ago; use 'all' for everything)")
    ap.add_argument("--out")
    ap.add_argument("--no-profile", action="store_true")
    a = ap.parse_args()
    if a.since.lower() == "all":
        a.since = "2010-10-06"  # Instagram launch date: fetch everything

    key = mindcase_key()
    if not key:
        sys.exit("NO_MINDCASE_KEY: no Mindcase key saved. Save one with: "
                 "config.py set-key <mk_live_...>")
    h = handle_of(a.handle)
    profile_url = f"https://www.instagram.com/{h}/"
    raw = {}

    account = {"username": h}
    if not a.no_profile:
        raw["profile"] = run_agent("profiles", {"usernames": [profile_url]}, key)
        prof = find_records(raw["profile"], {"followersCount", "followers", "followers_count",
                                             "username", "biography"})
        prof = (prof or [{}])[0]
        account.update({
            "username": pick(prof, "username") or h,
            "name": pick(prof, "fullName", "full_name", "name"),
            "biography": pick(prof, "biography", "bio"),
            "website": pick(prof, "externalUrl", "external_url", "website"),
            "followers_count": num(pick(prof, "followersCount", "followers", "followers_count",
                                        "edge_followed_by.count")),
            "follows_count": num(pick(prof, "followsCount", "following", "follows_count")),
            "media_count": num(pick(prof, "postsCount", "posts", "media_count", "mediaCount")),
            "is_verified": pick(prof, "verified", "isVerified", "is_verified"),
            "category": pick(prof, "businessCategoryName", "category", "category_name"),
        })

    posts, seen = [], set()
    for tab in [t.strip() for t in a.tab.split(",") if t.strip()]:
        raw[f"posts_{tab}"] = run_agent("posts", {"tab": tab, "handles": profile_url,
                                                  "onlyPostsNewerThan": a.since}, key)
        recs = find_records(raw[f"posts_{tab}"], {"caption", "likesCount", "shortCode", "shortcode",
                                                  "commentsCount", "timestamp", "url",
                                                  "videoPlayCount"}) or []
        for i, p in enumerate(recs):
            n = norm_post(p, f"{tab}-{i}")
            k = n["permalink"] or n["id"]
            if k in seen:
                continue
            seen.add(k)
            posts.append(n)

    json.dump(raw, open(f"{h}_mindcase_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out = a.out or f"{h}_posts.json"
    json.dump({"account": account, "posts": posts, "source": "mindcase", "tab": a.tab,
               "since": a.since}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    missing = [k for k in ("caption", "like_count", "timestamp") if not any(p.get(k) is not None for p in posts)]
    print(f"Saved {len(posts)} items ({a.tab}) for @{h} (followers: {account.get('followers_count')}) to {out}")
    if not posts:
        print(f"No post records found — inspect {h}_mindcase_raw.json (the run may still be in progress).")
    elif missing:
        print(f"Warning: no values for {missing}; check field names in {h}_mindcase_raw.json.")


if __name__ == "__main__":
    main()
