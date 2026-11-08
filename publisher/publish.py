#!/usr/bin/env python3
"""OWITH.ai publisher for GitHub Actions.

Reads the episode staged by the Claude cloud job on the `audio-inbox` branch, treats it as
untrusted input, validates it, uploads the MP3 to Buzzsprout, and writes a summary for the
workflow to turn into a GitHub Release (the permanent archive).

Secrets come only from the environment (GitHub encrypted secrets). Nothing here prints them.
Usage: python publish.py <staged_dir> <target_date YYYY-MM-DD> [--dry-run]
Exit codes: 0 published or already published, 2 nothing staged for the date, 1 error.
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Zurich")
PUBLISH_AT = time(7, 0)
MAX_MP3_MB = 60
ALLOWED_KEYS = {"title", "description", "tags", "publish_date", "kind"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def validate(d: Path, target: str) -> dict:
    meta = json.loads((d / "episode.json").read_text(encoding="utf-8"))
    extra = set(meta) - ALLOWED_KEYS
    if extra:
        raise ValueError(f"unexpected keys in episode.json: {sorted(extra)}")
    if meta.get("publish_date") != target:
        raise ValueError(f"staged episode is for {meta.get('publish_date')}, expected {target}")
    if meta.get("kind") not in ("daily", "saturday"):
        raise ValueError("kind must be daily or saturday")
    if not (5 <= len(meta.get("title", "")) <= 120):
        raise ValueError("title length out of bounds")
    if not (50 <= len(meta.get("description", "")) <= 9000):
        raise ValueError("description length out of bounds")
    if len(meta.get("tags", "")) > 300:
        raise ValueError("tags too long")
    mp3 = d / "episode.mp3"
    if mp3.stat().st_size > MAX_MP3_MB * 1024 * 1024 or mp3.stat().st_size < 200_000:
        raise ValueError("mp3 size out of bounds")
    head = mp3.read_bytes()[:3]
    if head != b"ID3" and head[:2] not in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        raise ValueError("episode.mp3 is not an MP3")
    render = json.loads((d / "render.json").read_text())
    if render.get("mp3_sha256") != sha256(mp3):
        raise ValueError("mp3 hash does not match render.json")
    if not 120 <= int(render.get("duration_sec", 0)) <= 600:
        raise ValueError("duration outside 2 to 10 minutes")
    return meta


def write_outputs(d: Path, out: dict, title: str) -> None:
    (d / "published.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out))
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"episode_number={out.get('episode_number') or ''}\n")
            f.write(f"title={title.replace(chr(10), ' ')}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("staged_dir")
    ap.add_argument("target_date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check-only", action="store_true",
                    help="validate staged files and test the token with a read only call; upload nothing")
    a = ap.parse_args()

    d = Path(a.staged_dir)
    if not (d / "episode.json").exists():
        print(f"::error::No episode staged for {a.target_date}")
        return 2
    meta = validate(d, a.target_date)

    token = os.environ["BUZZSPROUT_TOKEN"]
    pid = os.environ["BUZZSPROUT_PODCAST_ID"]
    api = f"https://www.buzzsprout.com/api/{pid}"
    headers = {"Authorization": f"Token token={token}"}

    r = requests.get(f"{api}/episodes.json", headers=headers, timeout=60)
    if r.status_code >= 400:
        print(f"::error::Buzzsprout returned HTTP {r.status_code} listing episodes (check token and podcast id)")
        return 1
    episodes = r.json()
    if a.check_only:
        latest = max((e.get("episode_number") or 0 for e in episodes), default=0)
        print(f"CHECK OK: staged files valid, token works, {len(episodes)} episodes on the feed, "
              f"latest number {latest}. Nothing uploaded.")
        return 0
    existing = next((e for e in episodes if e.get("title") == meta["title"]), None)
    if existing:
        print("Episode with this title already exists on Buzzsprout; skipping upload")
        write_outputs(d, {"buzzsprout_id": existing.get("id"),
                          "episode_number": existing.get("episode_number"),
                          "published_at": existing.get("published_at"),
                          "private": existing.get("private"), "skipped": True}, meta["title"])
        return 0
    number = max((e.get("episode_number") or 0 for e in episodes), default=0) + 1

    day = datetime.strptime(meta["publish_date"], "%Y-%m-%d").date()
    published_at = datetime.combine(day, PUBLISH_AT, TZ).isoformat()
    data = {
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta.get("tags", ""),
        "published_at": published_at,
        "episode_number": number,
        "explicit": "false",
        "private": "true" if a.dry_run else "false",
    }
    with open(d / "episode.mp3", "rb") as f:
        r = requests.post(f"{api}/episodes.json", headers=headers, data=data,
                          files={"audio_file": ("episode.mp3", f, "audio/mpeg")}, timeout=900)
    if r.status_code >= 400:
        print(f"::error::Buzzsprout returned HTTP {r.status_code}")
        return 1
    ep = r.json()
    write_outputs(d, {"buzzsprout_id": ep.get("id"), "episode_number": number,
                      "published_at": published_at, "private": a.dry_run}, meta["title"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
