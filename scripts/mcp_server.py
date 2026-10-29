#!/usr/bin/env python3
"""Local MCP server (stdio) for Instagram Content Analyser.

Runs on the user's own computer, started by the Claude desktop app, so it uses
the computer's normal internet connection. This avoids the cloud workspace's
network allowlist, which blocks api.mindcase.co.

Tools:
  fetch_account   fetch profile + reels/posts from Mindcase, cache, return metrics
  get_posts       page through cached posts (captions) for pillar classification
  pillar_stats    compute per-pillar stats from {post_id: pillar} tags
  export_posts    write the cached posts JSON/CSV to a folder on this computer
  status          key/profile/cache status

Pure standard library; needs only python3.
"""
import csv, json, os, re, statistics as st, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402

CACHE = Path(os.environ.get("IG_ANALYSER_CACHE")
             or Path.home() / ".cache" / "instagram-content-analyser")
SERVER = {"name": "instagram-content-analyser", "version": "0.4.0"}


def handle_of(s):
    s = (s or "").strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", s)
    return (m.group(1) if m else s).lstrip("@").strip("/").lower()


def posts_path(h):
    return CACHE / f"{h}_posts.json"


def run_script(args, timeout=1500):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([sys.executable, *args], cwd=CACHE, capture_output=True,
                       text=True, timeout=timeout)
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, out


def load_posts(h):
    f = posts_path(h)
    if not f.exists():
        raise ValueError(f"No cached data for @{h}. Call fetch_account first.")
    return json.loads(f.read_text(encoding="utf-8"))


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def eng(p):
    l, c = p.get("like_count"), p.get("comments_count")
    return None if l is None and c is None else (l or 0) + (c or 0)


def fmt(p):
    if (p.get("media_product_type") or "").upper() == "REELS":
        return "Reel"
    return {"CAROUSEL_ALBUM": "Carousel", "VIDEO": "Video", "IMAGE": "Image"}.get(
        (p.get("media_type") or "").upper(), "Other")


# ---------------- tools ----------------

def t_status(_):
    cached = sorted(f.name[:-11] for f in CACHE.glob("*_posts.json")) if CACHE.exists() else []
    cfg = config.load()
    return {"mindcase_key": bool(config.mindcase_key()), "profile": cfg.get("profile", {}),
            "profile_complete": all(cfg.get("profile", {}).get(k) for k in ("niche", "audience", "language")),
            "cache_dir": str(CACHE), "cached_accounts": cached}


def t_save_profile(a):
    cfg = config.load()
    prof = cfg.get("profile", {})
    for k, v in (a.get("fields") or a).items():
        if k != "fields" and v not in (None, ""):
            prof[k] = str(v).strip()
    if prof.get("handle"):
        prof["handle"] = handle_of(prof["handle"])
    cfg["profile"] = prof
    config.save(cfg)
    return {"saved": prof, "path": str(config.PATH)}


def t_fetch_account(a):
    h = handle_of(a.get("account"))
    if not h:
        raise ValueError("account is required (handle, @handle or profile URL)")
    if not config.mindcase_key():
        raise ValueError("NO_MINDCASE_KEY: no Mindcase key configured")
    f = posts_path(h)
    max_age = float(a.get("max_cache_hours", 24))
    if f.exists() and not a.get("refresh") and (time.time() - f.stat().st_mtime) < max_age * 3600:
        fetched = f"cache ({round((time.time() - f.stat().st_mtime) / 3600, 1)} h old)"
    else:
        args = [str(HERE / "fetch_mindcase.py"), h, "--tab", a.get("tab", "reels"),
                "--since", str(a.get("since", "all")), "--out", f.name]
        if a.get("include_profile") is False:
            args.append("--no-profile")
        ok, out = run_script(args)
        if not ok:
            raise ValueError(out[-1500:])
        fetched = out[-500:]
    ok, out = run_script([str(HERE / "analyze.py"), f.name, "--tz", a.get("timezone", "Asia/Kolkata"),
                          "--out", f"{h}_metrics.json"], timeout=300)
    if not ok:
        raise ValueError(out[-1500:])
    m = json.loads((CACHE / f"{h}_metrics.json").read_text(encoding="utf-8"))
    m.pop("posts_for_classification", None)
    return {"handle": h, "fetch": fetched, "posts_file": str(f), "metrics": m,
            "next": "Call get_posts to read captions for pillar classification."}


def t_get_posts(a):
    h = handle_of(a.get("account"))
    d = load_posts(h)
    posts = d["posts"]
    off, lim = int(a.get("offset", 0)), min(int(a.get("limit", 100)), 200)
    cc = int(a.get("caption_chars", 400))
    rows = [{"id": p.get("id"), "format": fmt(p), "date": (p.get("timestamp") or "")[:10],
             "views": p.get("view_count"), "engagement": eng(p),
             "caption": (p.get("caption") or "")[:cc], "permalink": p.get("permalink")}
            for p in posts[off:off + lim]]
    return {"handle": h, "total": len(posts), "offset": off, "returned": len(rows),
            "has_more": off + lim < len(posts), "posts": rows}


def t_pillar_stats(a):
    h = handle_of(a.get("account"))
    tags = a.get("tags") or {}
    if isinstance(tags, str):
        tags = json.loads(tags)
    d = load_posts(h)
    posts = d["posts"]
    by = defaultdict(list)
    untagged = 0
    for p in posts:
        k = tags.get(str(p.get("id")))
        if not k:
            untagged += 1
            continue
        by[k].append(p)
    all_eng = med([eng(p) for p in posts])
    all_views = med([p.get("view_count") for p in posts])
    n = sum(len(v) for v in by.values()) or 1
    out = {}
    for k, ps in sorted(by.items(), key=lambda kv: -len(kv[1])):
        e, v = med([eng(p) for p in ps]), med([p.get("view_count") for p in ps])
        fm = defaultdict(int)
        for p in ps:
            fm[fmt(p)] += 1
        out[k] = {"count": len(ps), "share_pct": round(len(ps) / n * 100, 1),
                  "median_engagement": e, "median_views": v,
                  "engagement_vs_account": round(e / all_eng, 2) if e and all_eng else None,
                  "views_vs_account": round(v / all_views, 2) if v and all_views else None,
                  "formats": dict(fm)}
    if a.get("save", True):
        (CACHE / f"{h}_pillars.json").write_text(json.dumps(tags, ensure_ascii=False), encoding="utf-8")
    return {"handle": h, "tagged": n if by else 0, "untagged": untagged,
            "account_median_engagement": all_eng, "account_median_views": all_views, "pillars": out}


def t_export_posts(a):
    h = handle_of(a.get("account"))
    d = load_posts(h)
    folder = Path(os.path.expanduser(a.get("folder") or "~/Documents/Instagram Content Analyser"))
    folder.mkdir(parents=True, exist_ok=True)
    j = folder / f"{h}_posts.json"
    j.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    c = folder / f"{h}_posts.csv"
    keys = ["id", "media_type", "media_product_type", "timestamp", "like_count", "comments_count",
            "view_count", "children_count", "permalink", "caption"]
    with open(c, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(d["posts"])
    return {"json": str(j), "csv": str(c), "posts": len(d["posts"])}


S = lambda **p: {"type": "object", "properties": p}  # noqa: E731
ACC = {"type": "string", "description": "Instagram handle, @handle or profile URL"}
TOOLS = {
    "status": (t_status, "Show whether the Mindcase key and creator profile are configured, and which accounts are cached.", S()),
    "save_profile": (t_save_profile, "Save or update the user's own creator profile on this computer (only the fields given change).",
        S(handle={"type": "string"}, niche={"type": "string"}, audience={"type": "string"},
          language={"type": "string"}, tone={"type": "string"}, goals={"type": "string"},
          offer={"type": "string"}, avoid={"type": "string"}, formats={"type": "string"})),
    "fetch_account": (t_fetch_account,
        "Fetch an Instagram account's profile and reels/posts from Mindcase (runs on the user's computer), cache them, and return computed metrics: format mix, cadence, timing, engagement, views, hooks, CTAs, hashtags, top/bottom posts. Results are cached for 24 h.",
        {**S(account=ACC,
             tab={"type": "string", "description": "reels (default), posts, or posts,reels"},
             since={"type": "string", "description": "YYYY-MM-DD or 'all' (default)"},
             timezone={"type": "string", "description": "IANA timezone for timing stats, default Asia/Kolkata"},
             refresh={"type": "boolean", "description": "Ignore cache and refetch"},
             include_profile={"type": "boolean"}), "required": ["account"]}),
    "get_posts": (t_get_posts, "Page through the cached posts of an account (id, format, date, views, engagement, caption, link) for reading and pillar classification.",
        {**S(account=ACC, offset={"type": "integer"}, limit={"type": "integer", "description": "max 200"},
             caption_chars={"type": "integer"}), "required": ["account"]}),
    "pillar_stats": (t_pillar_stats, "Given tags mapping every post id to one content pillar, compute count, share, median engagement/views and lift vs the account median per pillar.",
        {**S(account=ACC, tags={"type": "object", "description": "{post_id: pillar_name}"},
             save={"type": "boolean"}), "required": ["account", "tags"]}),
    "export_posts": (t_export_posts, "Write the cached posts of an account as JSON and CSV into a folder on the user's computer (default ~/Documents/Instagram Content Analyser).",
        {**S(account=ACC, folder={"type": "string"}), "required": ["account"]}),
}


def reply(i, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": i}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        m, i, params = req.get("method"), req.get("id"), req.get("params") or {}
        if i is None:  # notification
            continue
        if m == "initialize":
            reply(i, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {}}, "serverInfo": SERVER})
        elif m == "ping":
            reply(i, {})
        elif m == "tools/list":
            reply(i, {"tools": [{"name": n, "description": d, "inputSchema": s}
                                for n, (_, d, s) in TOOLS.items()]})
        elif m == "tools/call":
            name = params.get("name")
            if name not in TOOLS:
                reply(i, error={"code": -32602, "message": f"Unknown tool {name}"})
                continue
            try:
                res = TOOLS[name][0](params.get("arguments") or {})
                reply(i, {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, default=str)}]})
            except Exception as e:  # noqa: BLE001
                reply(i, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
        else:
            reply(i, error={"code": -32601, "message": f"Method not found: {m}"})


if __name__ == "__main__":
    main()
