#!/usr/bin/env python3
"""Download a Lib.ru work and save normalized UTF-8 text without overwriting."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


USER_AGENT = "libru-search-skill/1.0"
MAX_RESPONSE_BYTES = 50 * 1024 * 1024


class PreformattedTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pre_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "form", "select"}:
            self.skip_depth += 1
        elif tag == "pre":
            self.pre_depth += 1
        elif tag == "br" and self.pre_depth and not self.skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "form", "select"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "pre" and self.pre_depth:
            self.pre_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.pre_depth and not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts).strip()


def is_libru_host(hostname: str | None) -> bool:
    return bool(hostname and (hostname == "lib.ru" or hostname.endswith(".lib.ru")))


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use HTTP or HTTPS")
    if not is_libru_host(parsed.hostname):
        raise ValueError("URL must point to lib.ru or one of its subdomains")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not allowed")
    return value


def ascii_text_url(value: str) -> str | None:
    parsed = urlsplit(value)
    if not parsed.path.lower().endswith(".txt"):
        return None
    if parsed.path.lower().endswith("_ascii.txt"):
        return value
    scheme = "https"
    return urlunsplit((scheme, parsed.netloc, parsed.path + "_Ascii.txt", "", ""))


def fetch(value: str, timeout: float) -> tuple[bytes, str, str | None, str]:
    request = Request(value, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError("download exceeds 50 MiB")
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset()
        final_url = response.geturl()
    return data, content_type, charset, final_url


def decode_text(data: bytes, charset: str | None) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")

    encodings = [charset] if charset else []
    encodings.extend(["utf-8", "windows-1251", "koi8-r"])
    tried: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding.casefold() in tried:
            continue
        tried.add(encoding.casefold())
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    raise ValueError("could not decode the downloaded text")


def extract_text(decoded: str, content_type: str) -> str:
    if content_type == "text/html":
        parser = PreformattedTextParser()
        parser.feed(decoded)
        text = parser.text()
        if not text:
            raise ValueError("HTML page contains no preformatted work text")
    elif content_type.startswith("text/") or content_type in {
        "application/octet-stream",
        "application/x-empty",
    }:
        text = decoded
    else:
        raise ValueError(f"unsupported content type: {content_type}")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(char for char in text if char in {"\n", "\t"} or ord(char) >= 32)
    return text.strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a Lib.ru work and save normalized UTF-8 text."
    )
    parser.add_argument("url", help="direct Lib.ru work URL")
    parser.add_argument("output", type=Path, help="new UTF-8 text file")
    parser.add_argument("--timeout", type=float, default=30.0, help="network timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        source_url = validate_url(args.url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output.exists():
        print(f"error: output already exists: {args.output}", file=sys.stderr)
        return 2
    if not args.output.parent.is_dir():
        print(f"error: output directory does not exist: {args.output.parent}", file=sys.stderr)
        return 2

    download_url = ascii_text_url(source_url) or source_url
    try:
        try:
            data, content_type, charset, final_url = fetch(download_url, args.timeout)
        except HTTPError as exc:
            if download_url == source_url:
                raise
            data, content_type, charset, final_url = fetch(source_url, args.timeout)
        decoded = decode_text(data, charset)
        text = extract_text(decoded, content_type)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(text)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"error: failed to fetch text: {exc}", file=sys.stderr)
        return 2

    print(
        f"saved {len(text)} characters from {final_url} as UTF-8 to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
