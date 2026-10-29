#!/usr/bin/env python3
"""Fetch any public Instagram account's profile and posts/reels through the
Mindcase agents API, and normalise them to the plugin's posts JSON format.

Usage:
  fetch_mindcase.py <handle|@handle|profile URL> [--tab reels|posts|posts,reels]
                    [--since YYYY-MM-DD|all] [--out posts.json] [--no-profile]
                    [--max-wait SECONDS] [--new-job]

Mindcase flow: POST /agents/instagram/<agent>/run starts a job; if it is not
finished, poll GET /jobs/<id> until completed, then GET /jobs/<id>/results.
Job ids are remembered in <handle>_jobs.json so a re-run within 24 h reuses
the same job instead of paying for a new one (unless --new-job).

Progress is written to <handle>_progress.json while running.

Key: MINDCASE_API_KEY env var, else saved settings, else the plugin's
backend/mindcase.key (see config.py). MINDCASE_BASE_URL overrides the API base.
"""
import argparse, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import mindcase_key  # noqa: E402

BASE = os.environ.get("MINDCASE_BASE_URL", "https://api.mindcase.co/api/v1").rstrip("/")
DONE = {"completed", "succeeded", "success", "finished", "done"}
FAILED = {"failed", "cancelled", "canceled", "error"}
NOTICES = []


def handle_of(s):
    s = s.strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", s)
    return (m.group(1) if m else s).lstrip("@").strip("/")


def http(method, path, key, body=None, timeout=120):
    url = path if path.startswith("http") else f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(int(e.headers.get("Retry-After") or 5 * (attempt + 1)))
                continue
            hint = {401: "API key missing or invalid", 402: "Mindcase balance is empty — add balance at "
                    "https://console.mindcase.co/account?tab=billing",
                    403: "key not allowed to use this agent", 404: "not found"}.get(e.code, "")
            sys.exit(f"MINDCASE_HTTP_{e.code}: {hint} {txt}")
        except urllib.error.URLError as e:
            sys.exit(f"NETWORK_BLOCKED: cannot reach Mindcase ({e.reason}). This must run on a "
                     "computer with normal internet (the plugin's local connector).")
        except TimeoutError:
            if attempt < 3:
                continue
            sys.exit("MINDCASE_TIMEOUT: Mindcase did not answer in time.")


def note(resp):
    n = resp.get("notice") if isinstance(resp, dict) else None
    if n and n.get("message") and n["message"] not in NOTICES:
        NOTICES.append(n["message"])
        print(f"MINDCASE_NOTICE ({n.get('type')}): {n['message']}", flush=True)


def write_progress(h, **kw):
    try:
        p = f"{h}_progress.json"
        cur = json.load(open(p)) if os.path.exists(p) else {}
        cur.update(kw, updated=datetime.now(timezone.utc).isoformat())
        json.dump(cur, open(p, "w"), indent=1)
    except (OSError, ValueError):
        pass


def load_jobs(h):
    try:
        return json.load(open(f"{h}_jobs.json"))
    except (OSError, ValueError):
        jobs = {}
        # seed from an earlier raw response (older plugin versions)
        try:
            raw = json.load(open(f"{h}_mindcase_raw.json"))
            for k, v in raw.items():
                if isinstance(v, dict) and v.get("job_id") and k.startswith("posts_"):
                    jobs[f"posts|{k[6:]}|*"] = {"job_id": v["job_id"], "created_at": v.get("created_at")}
        except (OSError, ValueError):
            pass
        return jobs


def save_jobs(h, jobs):
    json.dump(jobs, open(f"{h}_jobs.json", "w"), indent=1)


def recent(created):
    try:
        t = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - t < timedelta(hours=24)
    except ValueError:
        return False


def results(job_id, key):
    """Download all rows of a finished job, following pagination if the API truncates."""
    first = http("GET", f"/jobs/{job_id}/results", key, timeout=300)
    note(first)
    rows = list(first.get("data") or []) if isinstance(first, dict) else list(first or [])
    total = None
    if isinstance(first, dict):
        total = int(first.get("row_count") or 0) or None
        truncated = str(first.get("truncated", "")).lower() == "true"
    else:
        truncated = False
    guard = 0
    while (truncated or (total and len(rows) < total)) and guard < 50:
        guard += 1
        q = urllib.parse.urlencode({"offset": len(rows), "limit": 500})
        nxt = http("GET", f"/jobs/{job_id}/results?{q}", key, timeout=300)
        more = (nxt.get("data") if isinstance(nxt, dict) else nxt) or []
        if not more or more[0] == rows[0]:  # API ignores pagination params
            break
        rows.extend(more)
        truncated = isinstance(nxt, dict) and str(nxt.get("truncated", "")).lower() == "true"
    return rows


def run_job(h, agent, params, key, max_wait, job_key=None, new_job=False):
    jobs = load_jobs(h) if job_key else {}
    prev = None
    if job_key and not new_job:
        prev = jobs.get(job_key) or jobs.get(job_key.rsplit("|", 1)[0] + "|*")
        if prev and not recent(prev.get("created_at")):
            prev = None
    if prev:
        job_id = prev["job_id"]
        print(f"Reusing Mindcase job {job_id} for {agent}", flush=True)
        st = http("GET", f"/jobs/{job_id}", key)
        if str(st.get("status", "")).lower() in FAILED and not st.get("row_count"):
            prev = None
        else:
            jobs[job_key] = prev
            save_jobs(h, jobs)
    if not prev:
        resp = http("POST", f"/agents/instagram/{agent}/run?wait=true", key, {"params": params}, timeout=170)
        note(resp)
        status = str(resp.get("status", "")).lower()
        if status in DONE and resp.get("data") is not None and str(resp.get("truncated", "")).lower() != "true":
            return resp.get("data") or [], resp
        job_id = resp.get("job_id") or resp.get("id")
        if not job_id:
            return resp.get("data") or [], resp
        if job_key:
            jobs[job_key] = {"job_id": job_id, "created_at": resp.get("created_at")
                             or datetime.now(timezone.utc).isoformat()}
            save_jobs(h, jobs)
    deadline = time.time() + max_wait
    st = {}
    while True:
        st = http("GET", f"/jobs/{job_id}", key)
        note(st)
        status = str(st.get("status", "")).lower()
        write_progress(h, agent=agent, job_id=job_id, status=status, row_count=st.get("row_count"),
                       usd_used=st.get("usd_used"))
        if status in DONE:
            break
        if status in FAILED:
            # a stopped run (e.g. balance hit $0) still keeps the rows delivered so far
            print(f"Mindcase job {job_id} ended with status '{status}': {st.get('error')}", flush=True)
            break
        if time.time() > deadline:
            sys.exit(f"MINDCASE_STILL_RUNNING: job {job_id} is still {status} "
                     f"({st.get('row_count') or 0} rows so far). Run again later to resume it.")
        time.sleep(5)
    rows = results(job_id, key)
    return rows, {**st, "job_id": job_id, "rows": len(rows)}


def find_records(obj, want):
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
        if cur not in (None, "", "None"):
            return cur
    return None


def num(v):
    if isinstance(v, bool):
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def boolish(v):
    return None if v is None else str(v).lower() == "true"


def norm_ts(v):
    if isinstance(v, (int, float)) and v > 1e9:
        return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, timezone.utc).isoformat()
    return v


def norm_post(p, i, tab):
    t = str(pick(p, "type", "media_type", "mediaType", "__typename") or "").lower()
    product = str(pick(p, "productType", "product_type", "media_product_type") or "").lower()
    children = pick(p, "childPosts", "children", "carousel_media", "sidecar", "images")
    url = pick(p, "postUrl", "url", "permalink", "link")
    is_reel = ("reel" in t or product in ("clips", "reels") or "clip" in t
               or (tab == "reels" and ("video" in t or not t)) or "/reel/" in str(url or ""))
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
    code = pick(p, "shortCode", "shortcode", "code")
    if not code and url:
        m = re.search(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", str(url))
        code = m.group(1) if m else None
    if not url and code:
        url = f"https://www.instagram.com/{'reel' if is_reel else 'p'}/{code}/"
    likes = num(pick(p, "likes", "likesCount", "like_count", "likeCount", "edge_liked_by.count"))
    if likes is not None and likes < 0:
        likes = None
    return {
        "id": str(pick(p, "id", "pk", "postId") or code or i),
        "caption": cap if isinstance(cap, str) else None,
        "media_type": mt, "media_product_type": pt,
        "like_count": likes,
        "comments_count": num(pick(p, "comments", "commentsCount", "comment_count", "comments_count")),
        "view_count": num(pick(p, "videoViews", "videoPlayCount", "playCount", "plays", "videoViewCount",
                               "views", "view_count", "play_count")),
        "timestamp": norm_ts(pick(p, "date", "timestamp", "takenAt", "taken_at", "createdAt", "postedAt")),
        "permalink": url,
        "children_count": len(children) if isinstance(children, list) and children else None,
        "duration_sec": pick(p, "videoDuration", "video_duration", "duration"),
        "music": pick(p, "musicInfo.song_name", "musicInfo.title", "music.title", "audio"),
        "is_pinned": boolish(pick(p, "pinned", "isPinned", "is_pinned")),
        "collaborators": pick(p, "coauthorProducers", "collaborators"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handle")
    ap.add_argument("--tab", default="reels", help="reels, posts, or both comma-separated")
    ap.add_argument("--since", default=(date.today() - timedelta(days=730)).isoformat(),
                    help="onlyPostsNewerThan YYYY-MM-DD, or 'all'")
    ap.add_argument("--out")
    ap.add_argument("--no-profile", action="store_true")
    ap.add_argument("--max-wait", type=int, default=1500, help="seconds to wait for a running job")
    ap.add_argument("--new-job", action="store_true", help="don't reuse a recent job")
    a = ap.parse_args()
    if a.since.lower() == "all":
        a.since = "2010-10-06"

    key = mindcase_key()
    if not key:
        sys.exit("NO_MINDCASE_KEY: no Mindcase key configured.")
    h = handle_of(a.handle)
    profile_url = f"https://www.instagram.com/{h}/"
    raw = {}
    write_progress(h, status="starting", handle=h, tab=a.tab, since=a.since, error=None)

    account = {"username": h}
    if not a.no_profile:
        write_progress(h, stage="profile")
        rows, meta = run_job(h, "profiles", {"usernames": [profile_url]}, key, 300)
        raw["profile"] = {"meta": meta, "data": rows}
        prof = (find_records(rows, {"followers", "followersCount", "username", "bio", "biography"}) or [{}])[0]
        links = pick(prof, "bioLinks") or []
        account.update({
            "username": pick(prof, "username") or h,
            "name": pick(prof, "fullName", "full_name", "name"),
            "biography": pick(prof, "bio", "biography"),
            "website": (links[0].get("url") if links and isinstance(links[0], dict) else None)
                       or pick(prof, "externalUrl", "external_url", "website"),
            "followers_count": num(pick(prof, "followers", "followersCount", "followers_count")),
            "follows_count": num(pick(prof, "following", "followsCount", "follows_count")),
            "media_count": num(pick(prof, "posts", "postsCount", "media_count", "mediaCount")),
            "is_verified": boolish(pick(prof, "verified", "isVerified", "is_verified")),
            "category": pick(prof, "businessCategory", "businessCategoryName", "category"),
            "last_post_date": pick(prof, "lastPostDate"),
        })

    posts, seen = [], set()
    for tab in [t.strip() for t in a.tab.split(",") if t.strip()]:
        write_progress(h, stage=f"posts:{tab}")
        rows, meta = run_job(h, "posts", {"tab": tab, "handles": profile_url, "onlyPostsNewerThan": a.since},
                             key, a.max_wait, job_key=f"posts|{tab}|{a.since}", new_job=a.new_job)
        raw[f"posts_{tab}"] = {"meta": meta, "rows": len(rows), "sample": rows[:3]}
        recs = find_records(rows, {"caption", "likes", "likesCount", "postUrl", "shortCode",
                                   "comments", "commentsCount", "date", "timestamp", "url"}) or []
        for i, p in enumerate(recs):
            n = norm_post(p, f"{tab}-{i}", tab)
            k = n["permalink"] or n["id"]
            if k in seen:
                continue
            seen.add(k)
            posts.append(n)

    json.dump(raw, open(f"{h}_mindcase_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out = a.out or f"{h}_posts.json"
    json.dump({"account": account, "posts": posts, "source": "mindcase", "tab": a.tab, "since": a.since,
               "notices": NOTICES, "fetched_at": datetime.now(timezone.utc).isoformat()},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_progress(h, status="done", stage="done", posts=len(posts))
    missing = [k for k in ("caption", "like_count", "timestamp") if not any(p.get(k) is not None for p in posts)]
    print(f"Saved {len(posts)} items ({a.tab}) for @{h} (followers: {account.get('followers_count')}) to {out}")
    if not posts:
        print(f"NO_POSTS: no post records returned — inspect {h}_mindcase_raw.json.")
    elif missing:
        print(f"Warning: no values for {missing}; check field names in {h}_mindcase_raw.json.")


if __name__ == "__main__":
    main()
