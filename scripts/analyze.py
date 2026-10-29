#!/usr/bin/env python3
"""Compute content metrics from a normalised posts JSON (output of fetch_ig.py).

Usage:
  analyze.py <posts.json> [--tz Asia/Kolkata] [--out metrics.json]

Produces format mix, cadence, timing, engagement by format, caption/hook stats,
hashtags, CTA usage, top/bottom posts, and a compact captions list for
Claude to classify into content pillars. Theme classification is NOT done here.
"""
import argparse, json, re, statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

CTA_PATTERNS = {
    "save": r"\bsave (this|it|for later)\b",
    "share": r"\b(share|send) (this|it) (with|to)\b|\btag (a|your)\b",
    "comment": r"\bcomment\b|\bdrop (a|an|your)\b|\blet me know\b",
    "follow": r"\bfollow (me|us|@|for)\b",
    "link_in_bio": r"\blink in (the )?bio\b",
    "dm": r"\bdm (me|us|you)\b|\bi.?ll dm\b|\bsend (me|us) a (dm|message)\b",
}
HOOK_TYPES = {
    "question": r"\?\s*$",
    "number_list": r"^\s*\d+\s+\w+",
    "how_to": r"^\s*how (to|i|we)\b",
    "stop_scroll": r"\b(stop|don't|do not|never|wait)\b",
    "you_address": r"^\s*(you|your)\b",
    "secret_mistake": r"\b(secret|mistake|nobody|no one|truth|myth)\b",
}


def fmt(p):
    if (p.get("media_product_type") or "").upper() == "REELS":
        return "Reel"
    return {"CAROUSEL_ALBUM": "Carousel", "VIDEO": "Video", "IMAGE": "Image"}.get(
        (p.get("media_type") or "").upper(), "Other")


def parse_ts(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    if re.match(r".*[+-]\d{4}$", s):
        s = s[:-2] + ":" + s[-2:]
    for f in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            d = datetime.fromisoformat(s) if f is None else datetime.strptime(s, f)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts")
    ap.add_argument("--tz", default="Asia/Kolkata")
    ap.add_argument("--out")
    a = ap.parse_args()
    data = json.load(open(a.posts, encoding="utf-8"))
    acct, posts = data["account"], data["posts"]
    tz = ZoneInfo(a.tz) if ZoneInfo else timezone.utc
    followers = acct.get("followers_count")

    rows = []
    for p in posts:
        cap = p.get("caption") or ""
        likes, comments = p.get("like_count"), p.get("comments_count")
        eng = None if likes is None and comments is None else (likes or 0) + (comments or 0)
        ts = parse_ts(p.get("timestamp"))
        lines = [l.strip() for l in cap.splitlines() if l.strip()]
        hook = lines[0][:160] if lines else ""
        rows.append({
            "id": p.get("id"), "format": fmt(p), "ts": ts, "likes": likes,
            "comments": comments, "views": p.get("view_count"), "eng": eng,
            "er": round(eng / followers * 100, 2) if eng is not None and followers else None,
            "caption": cap, "hook": hook, "words": len(cap.split()),
            "hashtags": [h.lower() for h in re.findall(r"#(\w+)", cap)],
            "mentions": re.findall(r"@([\w.]+)", cap),
            "ctas": [k for k, rx in CTA_PATTERNS.items() if re.search(rx, cap, re.I)],
            "hook_types": [k for k, rx in HOOK_TYPES.items() if re.search(rx, hook, re.I)],
            "slides": p.get("children_count"), "permalink": p.get("permalink"),
        })

    n = len(rows)
    dated = sorted([r for r in rows if r["ts"]], key=lambda r: r["ts"])
    out = {"account": acct, "post_count": n}
    likes_hidden = sum(1 for r in rows if r["likes"] is None)
    out["data_notes"] = {
        "posts_with_hidden_likes": likes_hidden,
        "posts_with_views": sum(1 for r in rows if r["views"] is not None),
        "followers_known": bool(followers),
    }

    # Cadence
    if len(dated) >= 2:
        span = (dated[-1]["ts"] - dated[0]["ts"]).days or 1
        gaps = [(b["ts"] - a_["ts"]).total_seconds() / 86400 for a_, b in zip(dated, dated[1:])]
        local = [r["ts"].astimezone(tz) for r in dated]
        out["cadence"] = {
            "first_post": dated[0]["ts"].date().isoformat(),
            "last_post": dated[-1]["ts"].date().isoformat(),
            "span_days": span,
            "posts_per_week": round(len(dated) / span * 7, 2),
            "median_gap_days": round(st.median(gaps), 2),
            "longest_gap_days": round(max(gaps), 1),
            "timezone": a.tz,
            "by_weekday": dict(Counter(d.strftime("%a") for d in local).most_common()),
            "by_hour": dict(sorted(Counter(d.hour for d in local).items())),
            "by_month": dict(sorted(Counter(d.strftime("%Y-%m") for d in local).items())),
        }

    # Formats
    byf = defaultdict(list)
    for r in rows:
        byf[r["format"]].append(r)
    out["formats"] = {
        f: {"count": len(rs), "share_pct": round(len(rs) / n * 100, 1),
            "median_engagement": med([r["eng"] for r in rs]),
            "median_er_pct": med([r["er"] for r in rs]),
            "median_views": med([r["views"] for r in rs]),
            "median_comments": med([r["comments"] for r in rs]),
            "median_slides": med([r["slides"] for r in rs]) if f == "Carousel" else None}
        for f, rs in sorted(byf.items(), key=lambda kv: -len(kv[1]))}

    # Engagement overall + trend (first half vs second half)
    out["engagement"] = {
        "median_engagement": med([r["eng"] for r in rows]),
        "median_er_pct": med([r["er"] for r in rows]),
        "median_likes": med([r["likes"] for r in rows]),
        "median_comments": med([r["comments"] for r in rows]),
        "median_views": med([r["views"] for r in rows]),
    }
    if len(dated) >= 10:
        h = len(dated) // 2
        out["engagement"]["trend"] = {
            "older_half_median": med([r["eng"] for r in dated[:h]]),
            "recent_half_median": med([r["eng"] for r in dated[h:]]),
        }

    # Captions, hooks, hashtags, CTAs
    tags = Counter(t for r in rows for t in r["hashtags"])
    eng_by_tag = defaultdict(list)
    for r in rows:
        for t in set(r["hashtags"]):
            eng_by_tag[t].append(r["eng"])
    words = [r["words"] for r in rows]
    buckets = {"short (<30 words)": [], "medium (30-120)": [], "long (>120)": []}
    for r in rows:
        k = "short (<30 words)" if r["words"] < 30 else "medium (30-120)" if r["words"] <= 120 else "long (>120)"
        buckets[k].append(r["eng"])
    out["captions"] = {
        "median_words": med(words),
        "engagement_by_length": {k: {"count": len(v), "median_engagement": med(v)} for k, v in buckets.items()},
        "median_hashtags_per_post": med([len(r["hashtags"]) for r in rows]),
        "top_hashtags": [{"tag": t, "uses": c, "median_engagement": med(eng_by_tag[t])}
                         for t, c in tags.most_common(20)],
        "cta_usage": {k: sum(1 for r in rows if k in r["ctas"]) for k in CTA_PATTERNS},
        "hook_types": dict(Counter(h for r in rows for h in r["hook_types"]).most_common()),
        "emoji_share_pct": round(sum(1 for r in rows if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", r["caption"])) / n * 100, 1) if n else 0,
        "top_mentions": Counter(m for r in rows for m in r["mentions"]).most_common(10),
    }

    def brief(r):
        return {"id": r["id"], "format": r["format"], "date": r["ts"].date().isoformat() if r["ts"] else None,
                "engagement": r["eng"], "views": r["views"], "er_pct": r["er"], "hook": r["hook"],
                "permalink": r["permalink"]}
    ranked = sorted([r for r in rows if r["eng"] is not None], key=lambda r: -r["eng"])
    out["top_posts"] = [brief(r) for r in ranked[:10]]
    out["bottom_posts"] = [brief(r) for r in ranked[-5:]] if len(ranked) > 15 else []

    # For Claude's pillar classification: compact list of every post
    out["posts_for_classification"] = [
        {"id": r["id"], "format": r["format"], "engagement": r["eng"],
         "caption": r["caption"][:400]} for r in rows]

    path = a.out or a.posts.replace(".json", "_metrics.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"Metrics for @{acct.get('username')} ({n} posts) saved to {path}")


if __name__ == "__main__":
    main()
