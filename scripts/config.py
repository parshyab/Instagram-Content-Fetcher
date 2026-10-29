#!/usr/bin/env python3
"""Private settings store for Instagram Content Analyser.

Stores the Mindcase API key and the user's own creator profile in a JSON file
OUTSIDE the plugin and repo, readable only by the current user:
  $IG_ANALYSER_CONFIG  or  ~/.config/instagram-content-analyser/config.json

Usage:
  config.py set-key <key|->         save Mindcase key ('-' reads it from stdin)
  config.py set-profile k=v [k=v]   save profile fields (handle, niche, audience,
                                    language, tone, goals, offer, avoid, ...)
  config.py show                    print settings with the key masked
  config.py status                  print which settings are present (JSON)
  config.py clear-key | clear-profile
"""
import json, os, stat, sys
from pathlib import Path

PATH = Path(os.environ.get("IG_ANALYSER_CONFIG")
            or Path.home() / ".config" / "instagram-content-analyser" / "config.json")


def load():
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save(cfg):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(PATH.parent, stat.S_IRWXU)
    except OSError:
        pass
    tmp = PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PATH)
    os.chmod(PATH, 0o600)


def mindcase_key():
    """Env var wins, then the saved settings file."""
    return os.environ.get("MINDCASE_API_KEY") or load().get("mindcase_api_key")


def mask(k):
    return (k[:8] + "…" + k[-4:]) if k and len(k) > 14 else ("set" if k else None)


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    cfg = load()
    if cmd == "set-key":
        key = sys.stdin.read().strip() if (not args or args[0] == "-") else args[0].strip()
        if not key.startswith("mk_"):
            sys.exit("That doesn't look like a Mindcase key (expected mk_live_... or mk_test_...).")
        cfg["mindcase_api_key"] = key
        save(cfg)
        print(f"Mindcase key saved ({mask(key)}) to {PATH}")
    elif cmd == "set-profile":
        prof = cfg.get("profile", {})
        for a in args:
            if "=" not in a:
                sys.exit(f"Expected key=value, got: {a}")
            k, v = a.split("=", 1)
            prof[k.strip()] = v.strip()
        if prof.get("handle"):
            prof["handle"] = prof["handle"].lstrip("@").split("instagram.com/")[-1].strip("/").split("?")[0]
        cfg["profile"] = prof
        save(cfg)
        print("Profile saved:", json.dumps(prof, ensure_ascii=False))
    elif cmd == "show":
        out = dict(cfg)
        if "mindcase_api_key" in out:
            out["mindcase_api_key"] = mask(out["mindcase_api_key"])
        print(json.dumps({"path": str(PATH), **out}, ensure_ascii=False, indent=2))
    elif cmd == "status":
        p = cfg.get("profile", {})
        print(json.dumps({"mindcase_key": bool(mindcase_key()),
                          "profile_complete": all(p.get(k) for k in ("niche", "audience", "language")),
                          "profile": p}, ensure_ascii=False))
    elif cmd == "clear-key":
        cfg.pop("mindcase_api_key", None); save(cfg); print("Key removed.")
    elif cmd == "clear-profile":
        cfg.pop("profile", None); save(cfg); print("Profile removed.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
