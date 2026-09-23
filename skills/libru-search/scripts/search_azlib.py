#!/usr/bin/env python3
"""Search az.lib.ru's classic collection and print concise UTF-8 TSV."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


SEARCH_URL = "http://az.lib.ru/cgi-bin/seek"
BASE_URL = "http://az.lib.ru/"
USER_AGENT = "Mozilla/5.0 (compatible; libru-search-skill/1.0)"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Candidate:
    author: str
    title: str
    url: str


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalized_http_url(value: str) -> str | None:
    url = urljoin(BASE_URL, value)
    parsed = urlsplit(url)
    if parsed.hostname not in {"az.lib.ru", "www.az.lib.ru"}:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    return urlunsplit(("http", "az.lib.ru", parsed.path, parsed.query, ""))


def author_directory(url: str) -> bool:
    parsed = urlsplit(url)
    parts = [part for part in parsed.path.split("/") if part]
    return parsed.path.endswith("/") and len(parts) == 2 and len(parts[0]) == 1


def work_url(url: str, author_url: str) -> bool:
    parsed = urlsplit(url)
    author_path = urlsplit(author_url).path
    name = parsed.path.rsplit("/", 1)[-1].casefold()
    if not parsed.path.startswith(author_path) or parsed.path.endswith("/"):
        return False
    if name.startswith("index"):
        return False
    return name.endswith((".shtml", ".html", ".txt"))


class ClassicSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.link_href: str | None = None
        self.link_parts: list[str] = []
        self.current_author = ""
        self.current_author_url = ""
        self.candidates: list[Candidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self.link_href is not None:
            return
        href = dict(attrs).get("href")
        if href:
            self.link_href = href
            self.link_parts = []

    def handle_data(self, data: str) -> None:
        if self.link_href is not None:
            self.link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self.link_href is not None:
            self._finish_link()

    def _finish_link(self) -> None:
        href = self.link_href or ""
        text = clean_text("".join(self.link_parts))
        self.link_href = None
        self.link_parts = []
        url = normalized_http_url(href)
        if not text or not url:
            return

        if author_directory(url):
            self.current_author = text
            self.current_author_url = url
            return

        if self.current_author_url and work_url(url, self.current_author_url):
            self.candidates.append(Candidate(self.current_author, text, url))


def build_search_url(query: str) -> str:
    try:
        query_bytes = query.encode("windows-1251")
    except UnicodeEncodeError as exc:
        bad = query[exc.start : exc.end]
        raise ValueError(
            f"query contains characters unavailable in Windows-1251: {bad!r}"
        ) from exc

    parameters = [
        ("DIR", b""),
        ("PLACE", b"index"),
        ("FIND", query_bytes),
        ("JANR", b"0"),
        ("TYPE", b"0"),
    ]
    return SEARCH_URL + "?" + urlencode(parameters)


def fetch_results(query: str, timeout: float) -> list[Candidate]:
    request = Request(build_search_url(query), headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("search response exceeds 10 MiB")
            charset = response.headers.get_content_charset() or "windows-1251"
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"az.lib.ru search request failed: {exc}") from exc

    try:
        page = data.decode(charset, errors="replace")
    except LookupError as exc:
        raise RuntimeError(f"unsupported response charset: {charset}") from exc

    parser = ClassicSearchParser()
    parser.feed(page)
    unique: dict[str, Candidate] = {}
    for candidate in parser.candidates:
        unique.setdefault(candidate.url, candidate)
    return list(unique.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search az.lib.ru classics and print UTF-8 TSV."
    )
    parser.add_argument("query", help="title or author fragment")
    parser.add_argument("--limit", type=int, default=10, help="maximum results (default: 10)")
    parser.add_argument("--timeout", type=float, default=15.0, help="network timeout in seconds")
    args = parser.parse_args()
    if not 1 <= args.limit <= 60:
        parser.error("--limit must be between 1 and 60")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    query = clean_text(args.query)
    if not query:
        print("error: empty query", file=sys.stderr)
        return 2

    try:
        candidates = fetch_results(query, args.timeout)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("rank\tkind\tauthor_or_section\ttitle\turl")
    for rank, candidate in enumerate(candidates[: args.limit], start=1):
        fields = (str(rank), "work", candidate.author, candidate.title, candidate.url)
        print("\t".join(clean_text(field).replace("\t", " ") for field in fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
