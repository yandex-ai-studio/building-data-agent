#!/usr/bin/env python3
"""Search Lib.ru's legacy title index and print concise UTF-8 TSV."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote_from_bytes, urljoin, urlsplit
from urllib.request import Request, urlopen


SEARCH_URL = "https://lib.ru/GrepSearch?Search="
BASE_URL = "https://lib.ru/"
USER_AGENT = "libru-search-skill/1.0"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Candidate:
    kind: str
    context: str
    title: str
    url: str
    order: int


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return " ".join(re.findall(r"[0-9a-zа-я]+", value))


def infer_author_prefix(context: str, title: str) -> tuple[str, str]:
    match = re.match(r"^(.+?)\.\s+(.+)$", title)
    if not match:
        return context, title
    prefix, remainder = match.groups()
    words = prefix.split()
    if not 2 <= len(words) <= 4:
        return context, title
    if not all(word and word[0].isalpha() and word[0].isupper() for word in words):
        return context, title
    return prefix, remainder


class CatalogSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_heading = False
        self.heading_parts: list[str] = []
        self.in_results = False
        self.link_href: str | None = None
        self.link_parts: list[str] = []
        self.current_context = ""
        self.directories: list[Candidate] = []
        self.works: list[Candidate] = []
        self._order = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "h3":
            self.in_heading = True
            self.heading_parts = []
            return
        if tag == "a" and self.in_results and self.link_href is None:
            href = dict(attrs).get("href")
            if href:
                self.link_href = href
                self.link_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading_parts.append(data)
        if self.link_href is not None:
            self.link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h3" and self.in_heading:
            heading = clean_text("".join(self.heading_parts)).casefold()
            self.in_results = heading.startswith("поиск по оглавлению библиотеки")
            self.in_heading = False
            self.heading_parts = []
            return
        if tag == "a" and self.link_href is not None:
            self._finish_link()

    def _finish_link(self) -> None:
        href = self.link_href or ""
        text = clean_text("".join(self.link_parts))
        self.link_href = None
        self.link_parts = []
        if not text:
            return

        url = urljoin(BASE_URL, href)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "lib.ru",
            "www.lib.ru",
        }:
            return

        self._order += 1
        is_directory = (
            parsed.path.endswith("/")
            or parsed.path.casefold().endswith(".dir")
            or text.casefold().startswith("[dir]")
        )
        if is_directory:
            context = re.sub(r"^\[dir\]\s*", "", text, flags=re.IGNORECASE)
            context = re.sub(r"\s+\([^()]+/\)\s*$", "", context)
            if parsed.path.endswith("/"):
                self.current_context = context
            self.directories.append(
                Candidate("directory", context, context, url, self._order)
            )
            return

        context, title = infer_author_prefix(self.current_context, text)
        self.works.append(Candidate("work", context, title, url, self._order))


def candidate_score(candidate: Candidate, query: str) -> tuple[int, int, int, int]:
    title = normalized(candidate.title)
    context = normalized(candidate.context)
    needle = normalized(query)
    if context and title.startswith(context + " "):
        title = title[len(context) + 1 :]
    elif "." in candidate.title:
        suffix = normalized(candidate.title.split(".", 1)[1])
        if needle in suffix:
            title = suffix

    if title == needle:
        match_rank = 0
    elif title.startswith(needle + " "):
        match_rank = 1
    elif needle in title:
        match_rank = 2
    elif all(token in title for token in needle.split()):
        match_rank = 3
    else:
        match_rank = 4

    secondary_terms = (
        "переписан",
        "отрывок",
        "фрагмент",
        "анализ",
        "реценз",
        "критик",
        "о фильме",
        "комментар",
    )
    secondary_penalty = int(any(term in title for term in secondary_terms))
    return secondary_penalty, match_rank, len(title), candidate.order


def search_term(query: str) -> str:
    stopwords = {"а", "без", "в", "во", "для", "и", "из", "к", "на", "не", "о", "об", "от", "по", "с", "у"}
    tokens = normalized(query).split()
    for token in tokens:
        if len(token) >= 3 and token not in stopwords:
            return token
    return query


def fetch_results(query: str, timeout: float) -> list[Candidate]:
    term = search_term(query)
    try:
        query_bytes = term.encode("windows-1251")
    except UnicodeEncodeError as exc:
        bad = query[exc.start : exc.end]
        raise ValueError(
            f"query contains characters unavailable in Windows-1251: {bad!r}"
        ) from exc

    url = SEARCH_URL + quote_from_bytes(query_bytes)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("search response exceeds 10 MiB")
            charset = response.headers.get_content_charset() or "windows-1251"
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Lib.ru search request failed: {exc}") from exc

    try:
        page = data.decode(charset, errors="replace")
    except LookupError as exc:
        raise RuntimeError(f"unsupported response charset: {charset}") from exc

    parser = CatalogSearchParser()
    parser.feed(page)
    candidates = parser.works if parser.works else parser.directories

    query_tokens = [token for token in normalized(query).split() if len(token) >= 2]
    full_matches = [
        candidate
        for candidate in candidates
        if all(token in normalized(candidate.title) for token in query_tokens)
    ]
    if full_matches:
        candidates = full_matches

    unique: dict[str, Candidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.url, candidate)
    return sorted(unique.values(), key=lambda item: candidate_score(item, query))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Lib.ru by a title fragment and print UTF-8 TSV."
    )
    parser.add_argument("query", help="title fragment")
    parser.add_argument("--limit", type=int, default=5, help="maximum results (default: 5)")
    parser.add_argument("--timeout", type=float, default=30.0, help="network timeout in seconds")
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error("--limit must be between 1 and 50")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    query = clean_text(args.query).lower()
    if not query:
        print("error: empty query", file=sys.stderr)
        return 2

    try:
        candidates = fetch_results(query, args.timeout)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not candidates:
        print("No matching Lib.ru catalog entries found.", file=sys.stderr)
        return 1

    print("rank\tkind\tauthor_or_section\ttitle\turl")
    for rank, candidate in enumerate(candidates[: args.limit], start=1):
        fields = (
            str(rank),
            candidate.kind,
            candidate.context or "-",
            candidate.title,
            candidate.url,
        )
        print("\t".join(field.replace("\t", " ") for field in fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
