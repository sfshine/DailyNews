#!/usr/bin/env python3
"""Generate a daily technology intelligence report in Markdown.

The script intentionally uses only Python's standard library so it can run in a
minimal GitHub Actions environment. It aggregates public RSS/API endpoints for
three watch areas: mobile frontend, AI coding, and embodied AI.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"

@dataclass(frozen=True)
class FeedConfig:
    name: str
    query: str
    category: str

FEEDS = [
    FeedConfig("Google News", "Android OR Flutter OR React Native mobile frontend developer", "移动大前端"),
    FeedConfig("Google News", "AI coding agent OR GitHub Copilot OR Cursor OR Claude Code OR Codex", "AI Coding"),
    FeedConfig("Google News", "embodied AI OR humanoid robot OR physical AI robotics", "具身人工智能"),
]

ARXIV_QUERIES = [
    ("AI Coding", 'cat:cs.SE AND ("coding agent" OR "software engineering agent" OR "program repair")'),
    ("具身人工智能", 'cat:cs.RO AND ("embodied AI" OR "humanoid" OR "robot foundation model")'),
]


def fetch_url(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DailyNewsBot/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec: public feeds only
        return response.read()


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def google_news_url(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "hl": "zh-CN", "gl": "US", "ceid": "US:zh-Hans"})
    return f"https://news.google.com/rss/search?{params}"


def parse_google_news(feed: FeedConfig, limit: int = 5) -> list[dict[str, str]]:
    xml_bytes = fetch_url(google_news_url(feed.query))
    root = ET.fromstring(xml_bytes)
    items: list[dict[str, str]] = []
    for item in root.findall("./channel/item")[:limit]:
        items.append({
            "category": feed.category,
            "title": clean_text(item.findtext("title")),
            "link": clean_text(item.findtext("link")),
            "published": clean_text(item.findtext("pubDate")),
            "source": feed.name,
        })
    return items


def arxiv_url(query: str) -> str:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": 3,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    return f"https://export.arxiv.org/api/query?{params}"


def parse_arxiv(category: str, query: str) -> list[dict[str, str]]:
    xml_bytes = fetch_url(arxiv_url(query))
    root = ET.fromstring(xml_bytes)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        link = ""
        for candidate in entry.findall("atom:link", ns):
            if candidate.attrib.get("rel") == "alternate":
                link = candidate.attrib.get("href", "")
                break
        items.append({
            "category": category,
            "title": clean_text(entry.findtext("atom:title", namespaces=ns)),
            "link": link,
            "published": clean_text(entry.findtext("atom:published", namespaces=ns)),
            "source": "arXiv",
        })
    return items


def render_report(report_date: dt.date, items: list[dict[str, str]]) -> str:
    grouped: dict[str, list[dict[str, str]]] = {"移动大前端": [], "AI Coding": [], "具身人工智能": []}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)

    lines = [
        f"# 技术情报日报 - {report_date.isoformat()}",
        "",
        f"> 自动生成时间：{dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}",
        "> 聚焦方向：移动大前端、AI Coding、具身人工智能。",
        "",
        "## 今日速览",
        "",
    ]
    for category, category_items in grouped.items():
        lines.append(f"- **{category}**：抓取到 {len(category_items)} 条候选情报。")
    lines.append("")

    for category, category_items in grouped.items():
        lines.extend([f"## {category}", ""])
        if not category_items:
            lines.extend(["暂无抓取结果。", ""])
            continue
        for index, item in enumerate(category_items, start=1):
            title = item["title"] or "Untitled"
            link = item["link"] or "#"
            published = item["published"] or "unknown time"
            source = item["source"]
            lines.extend([
                f"### {index}. [{title}]({link})",
                "",
                f"- 来源：{source}",
                f"- 发布时间：{published}",
                "- 初步研判：需结合原文进一步确认技术细节、适配成本和落地窗口。",
                "",
            ])

    lines.extend([
        "## 跟进建议",
        "",
        "1. 优先打开官方发布、论文或厂商技术博客，确认 API/版本号/可用性。",
        "2. 对影响研发效率或架构选型的内容，补充 POC、迁移风险和竞品对比。",
        "3. 对机器人/具身智能信息，区分演示、论文结果、试点部署和规模化量产。",
        "",
    ])
    return "\n".join(lines)


def generate(report_date: dt.date, output_dir: Path = REPORTS_DIR) -> Path:
    items: list[dict[str, str]] = []
    errors: list[str] = []
    for feed in FEEDS:
        try:
            items.extend(parse_google_news(feed))
        except Exception as exc:  # noqa: BLE001 - report generation should degrade gracefully
            errors.append(f"{feed.category}/{feed.name}: {exc}")
    for category, query in ARXIV_QUERIES:
        try:
            items.extend(parse_arxiv(category, query))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{category}/arXiv: {exc}")

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report_date.isoformat()}.md"
    content = render_report(report_date, items)
    if errors:
        content += "\n## 抓取异常\n\n" + "\n".join(f"- {error}" for error in errors) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Report date in YYYY-MM-DD format")
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR, help="Directory for generated reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        report_date = dt.date.fromisoformat(args.date)
    except ValueError as exc:
        raise SystemExit(f"Invalid --date value: {args.date!r}") from exc
    path = generate(report_date, args.output_dir)
    
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    print(f"Generated {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
