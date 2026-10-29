#!/usr/bin/env python3
"""Fetch another Instagram Business/Creator account's public posts via the
official Graph API Business Discovery endpoint, or normalise supplied data.

Usage:
  fetch_ig.py api <username> [--limit N] [--out posts.json]
  fetch_ig.py file <path.csv|path.json> --username <name> [--followers N] [--out posts.json]

Env (api mode):
  IG_ACCESS_TOKEN   Instagram User access token (Instagram API with Facebook Login)
  IG_USER_ID        Your own IG Business/Creator user ID (the account making the query)
  IG_GRAPH_VERSION  Optional, defaults to v25.0

Output: a normalised JSON file:
  {"account": {...}, "posts": [{id, caption, media_type, media_product_type,
   like_count, comments_count, view_count, timestamp, permalink, children_count}]}
"""
import argparse, csv, json, os, sys, time, urllib.parse, urllib.request, urllib.error

MEDIA_FIELDS = ("id,caption,media_type,media_product_type,like_count,comments_count,"
                "view_count,timestamp,permalink,children{id,media_type}")
ACCOUNT_FIELDS = "username,name,biography,website,followers_count,follows_count,media_count"


def _get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            try:
                err = json.loads(body).get("error", {})
            except ValueError:
                err = {"message": body[:300]}
            # view_count is not available on every API version/account: retry without it
            if "view_count" in url and "view_count" in str(err.get("message", "")):
                return {"_retry_without_view_count": True}
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 ** attempt * 3)
                continue
            sys.exit(f"Graph API error {e.code}: {err.get('message')} (code {err.get('code')})")
        except urllib.error.URLError as e:
            sys.exit(f"Network error reaching graph.facebook.com: {e.reason}")


def fetch_api(username, limit):
    token = os.environ.get("IG_ACCESS_TOKEN")
    me = os.environ.get("IG_USER_ID")
    ver = os.environ.get("IG_GRAPH_VERSION", "v25.0")
    if not token or not me:
        sys.exit("Missing IG_ACCESS_TOKEN or IG_USER_ID. See references/graph-api-setup.md.")
    media_fields = MEDIA_FIELDS
    posts, after, account = [], None, None
    while len(posts) < limit:
        page = min(50, limit - len(posts))
        cursor = f".after({after})" if after else ""
        fields = (f"business_discovery.username({username})"
                  f"{{{ACCOUNT_FIELDS},media{cursor}.limit({page}){{{media_fields}}}}}")
        url = (f"https://graph.facebook.com/{ver}/{me}?"
               + urllib.parse.urlencode({"fields": fields, "access_token": token}))
        data = _get(url)
        if data.get("_retry_without_view_count"):
            media_fields = media_fields.replace("view_count,", "")
            continue
        bd = data.get("business_discovery")
        if not bd:
            sys.exit(f"No data for @{username}. It must be a public Business or Creator account "
                     "that is not age-gated.")
        if account is None:
            account = {k: bd.get(k) for k in ACCOUNT_FIELDS.split(",")}
        media = bd.get("media", {})
        batch = media.get("data", [])
        posts.extend(batch)
        after = media.get("paging", {}).get("cursors", {}).get("after")
        if not batch or not after:
            break
        time.sleep(0.5)
    for p in posts:
        p["children_count"] = len((p.pop("children", None) or {}).get("data", []))
    return account, posts[:limit]


def _num(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def load_file(path, username, followers):
    if path.lower().endswith(".json"):
        raw = json.load(open(path, encoding="utf-8"))
        rows = raw.get("posts", raw) if isinstance(raw, dict) else raw
    else:
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    alias = {
        "caption": ["caption", "text", "description"],
        "media_type": ["media_type", "type", "format"],
        "media_product_type": ["media_product_type", "product_type"],
        "like_count": ["like_count", "likes"],
        "comments_count": ["comments_count", "comments"],
        "view_count": ["view_count", "views", "plays"],
        "timestamp": ["timestamp", "date", "posted_at", "created_at"],
        "permalink": ["permalink", "url", "link"],
        "children_count": ["children_count", "slides"],
    }
    posts = []
    for i, r in enumerate(rows):
        low = {str(k).strip().lower(): v for k, v in r.items()}
        p = {"id": low.get("id") or str(i)}
        for key, names in alias.items():
            p[key] = next((low[n] for n in names if low.get(n) not in (None, "")), None)
        for k in ("like_count", "comments_count", "view_count", "children_count"):
            p[k] = _num(p[k])
        mt = (p["media_type"] or "").upper()
        if mt in ("REEL", "REELS", "VIDEO"):
            p["media_type"], p["media_product_type"] = "VIDEO", p["media_product_type"] or "REELS"
        elif mt in ("CAROUSEL", "CAROUSEL_ALBUM", "SIDECAR"):
            p["media_type"] = "CAROUSEL_ALBUM"
        elif mt:
            p["media_type"] = "IMAGE" if mt in ("IMAGE", "PHOTO", "POST") else mt
        posts.append(p)
    account = {"username": username, "followers_count": followers, "media_count": len(posts)}
    return account, posts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["api", "file"])
    ap.add_argument("target", help="username (api) or file path (file)")
    ap.add_argument("--username")
    ap.add_argument("--followers", type=int)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.mode == "api":
        uname = a.target.lstrip("@")
        account, posts = fetch_api(uname, a.limit)
    else:
        uname = (a.username or "account").lstrip("@")
        account, posts = load_file(a.target, uname, a.followers)
    out = a.out or f"{uname}_posts.json"
    json.dump({"account": account, "posts": posts}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"Saved {len(posts)} posts for @{uname} to {out}")


if __name__ == "__main__":
    main()
