"""Check CW3E's "S&S Outlooks" feed for a new subseasonal outlook post.

Run weekly (workflow s2s_update.yml). Prints key=value lines to $GITHUB_OUTPUT: `new=true|false`, and the
latest post's title and link. The newest post seen so far is kept in data/s2s/last_seen.json; the first run only
records it (no alert). The workflow turns `new=true` into a GitHub issue, which emails the repo owner.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

FEED = "https://cw3e-sites.ucsd.edu/category/ss-outlooks/feed/"
STATE = Path(__file__).resolve().parent.parent / "data" / "s2s" / "last_seen.json"


def latest_post():
    r = requests.get(FEED, timeout=60, headers={"User-Agent": "cascade-mountain-weather (weekly check)"})
    r.raise_for_status()
    item = ET.fromstring(r.content).find("./channel/item")
    if item is None:
        raise ValueError("no posts in the feed")
    return {k: (item.findtext(k) or "").strip() for k in ("title", "link", "pubDate")}


def emit(**kv):
    lines = [f"{k}={v}" for k, v in kv.items()]
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    post = latest_post()
    seen = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    is_new = bool(seen) and seen.get("link") != post["link"]
    if not seen or is_new:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(post, indent=1), encoding="utf-8")
    emit(new="true" if is_new else "false", title=post["title"], link=post["link"], published=post["pubDate"])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"S2S check failed: {e}", file=sys.stderr)
        sys.exit(1)
