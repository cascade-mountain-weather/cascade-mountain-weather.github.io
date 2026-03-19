#!/usr/bin/env python3
"""Generate sitemap.xml for cascademountainweather.com.

This script scans key pages, posts, and tool pages, then writes sitemap.xml
with deterministic ordering and per-file last modified dates from git.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SITEMAP_PATH = ROOT / "sitemap.xml"
BASE_URL = "https://www.cascademountainweather.com"


@dataclass(frozen=True)
class UrlEntry:
    rel_path: str
    changefreq: str
    priority: str
    section: str


def run_git_lastmod(rel_path: str) -> str:
    """Return YYYY-MM-DD from git history for the file, fallback to today (UTC)."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if value:
            return value
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def url_from_rel(rel_path: str) -> str:
    if rel_path == "index.html":
        return f"{BASE_URL}/"
    return f"{BASE_URL}/{rel_path}"


def discover_posts() -> list[UrlEntry]:
    posts_dir = ROOT / "posts"
    post_files = sorted(posts_dir.glob("*-weekend-forecast.html"), reverse=True)
    entries: list[UrlEntry] = [
        UrlEntry(
            rel_path="posts/archive.html",
            changefreq="weekly",
            priority="0.7",
            section="Posts",
        )
    ]

    for file_path in post_files:
        name = file_path.name
        prio = "0.8" if len(entries) <= 2 else "0.7"
        entries.append(
            UrlEntry(
                rel_path=f"posts/{name}",
                changefreq="yearly",
                priority=prio,
                section="Posts",
            )
        )

    return entries


def discover_tools() -> list[UrlEntry]:
    tools_dir = ROOT / "tools"
    tools = sorted(p.name for p in tools_dir.glob("*.html"))

    high_priority = {
        "mt-baker.html",
        "stevens-pass.html",
        "snoqualmie-pass.html",
        "crystal-mountain.html",
        "model-tools-current-weather.html",
    }
    medium_priority = {
        "white-pass.html",
        "paradise.html",
    }

    entries: list[UrlEntry] = []
    for tool_name in tools:
        if tool_name in high_priority:
            priority = "0.9"
        elif tool_name in medium_priority:
            priority = "0.8"
        else:
            priority = "0.7"

        changefreq = "hourly" if tool_name == "model-tools-current-weather.html" else "daily"
        entries.append(
            UrlEntry(
                rel_path=f"tools/{tool_name}",
                changefreq=changefreq,
                priority=priority,
                section="Ski Area Tools",
            )
        )

    return entries


def build_entries() -> list[UrlEntry]:
    main_pages = [
        UrlEntry("index.html", "daily", "1.0", "Main Pages"),
        UrlEntry("about.html", "monthly", "0.8", "Main Pages"),
        UrlEntry("evaluation.html", "weekly", "0.8", "Main Pages"),
        UrlEntry("model-tools.html", "monthly", "0.8", "Main Pages"),
        UrlEntry("sitemap-page.html", "monthly", "0.6", "Main Pages"),
    ]
    return [*main_pages, *discover_posts(), *discover_tools()]


def indent_xml(elem: ET.Element, level: int = 0) -> None:
    """Pretty-print helper for xml.etree output."""
    indent = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = indent
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = indent


def build_xml(entries: list[UrlEntry]) -> str:
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    current_section = None
    for entry in entries:
        if entry.section != current_section:
            urlset.append(ET.Comment(f" {entry.section} "))
            current_section = entry.section

        node = ET.SubElement(urlset, "url")
        ET.SubElement(node, "loc").text = url_from_rel(entry.rel_path)
        ET.SubElement(node, "lastmod").text = run_git_lastmod(entry.rel_path)
        ET.SubElement(node, "changefreq").text = entry.changefreq
        ET.SubElement(node, "priority").text = entry.priority

    indent_xml(urlset)
    body = ET.tostring(urlset, encoding="unicode")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + body + "\n"


def main() -> None:
    entries = build_entries()
    xml_text = build_xml(entries)
    SITEMAP_PATH.write_text(xml_text, encoding="utf-8")
    print(f"Updated {SITEMAP_PATH.relative_to(ROOT)} with {len(entries)} URLs")


if __name__ == "__main__":
    main()