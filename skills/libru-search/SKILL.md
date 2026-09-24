---
name: libru-search
description: Find books and authors in Maxim Moshkov's Lib.ru library, return verified links, and download texts for local mechanical analysis. Use for Lib.ru catalog, title, author, and text-processing requests; do not use it to reproduce whole books in chat.
---

# Lib.ru search

Work in a Unix environment. Prefer `python3`, `curl`, `iconv`, `rg`/`grep`, `sort`, `uniq`, and `awk`. Use short one-off Python only when ordinary command-line tools are insufficient.

Resolve this skill's directory as `SKILL_DIR`; the reusable commands live in `scripts/` below it.

## Find Russian classics

For Russian classic authors and works, search Lib.ru's classic collection at `http://az.lib.ru/` first:

```sh
python3 "$SKILL_DIR/scripts/search_azlib.py" "title or author fragment" --limit 10 --timeout 15
```

The script makes one HTTP GET request to `http://az.lib.ru/cgi-bin/seek`, encodes the query as Windows-1251, and emits UTF-8 TSV. It does not follow result pages or crawl the catalog. Verify a promising result on its work or author page. If the classic search has no suitable match, fall back to the general Lib.ru search below.

The classic collection also supports browsing:

- Search form: `http://az.lib.ru/cgi-bin/seek`
- Genres: `http://az.lib.ru/janr/`
- Literary forms: `http://az.lib.ru/type/`
- Literary affiliation and periods: `http://az.lib.ru/rating/litarea/`
- Ratings: `http://az.lib.ru/rating/top40/` and `http://az.lib.ru/rating/top100/`
- New additions: `http://az.lib.ru/long.shtml`

Genre and form pages offer views sorted by rating, update time, year, title, and reader count. Use these indexes when a fragment search is too broad or the user wants to browse rather than identify one work.

## Find other books

Search by a distinctive title fragment first:

```sh
python3 "$SKILL_DIR/scripts/search_libru.py" "title fragment" --limit 5
```

This script sends the required `https://lib.ru/GrepSearch?Search=...` request using the Windows-1251 encoding expected by the legacy CGI and emits UTF-8 TSV. Treat `author_or_section` as context to verify, not always as a canonical author name.

Review at most five candidates. Prefer an exact title and matching author, then a complete work over excerpts, rewritten chapters, reviews, criticism, or mentions. Open the selected work or its author directory and verify the title before claiming a match. If ambiguity remains, show the candidates instead of guessing.

For an author supplied by the user, use the UTF-8 catalog as an auxiliary check:

```sh
curl -fsSL http://aot.ru/authors.html \
  | sed 's/<br>/\n/g' \
  | sed -E 's/<[^>]+>//g' \
  | grep -iF -- "$author"
```

Retry a surname, initials, and `е`/`ё` variants. Absence from this catalog is not proof that Lib.ru lacks the author: still use the title search and relevant catalog pages.

## Catalog fallbacks

Download and search only the likely indexes; do not crawl every section. Inspect `Content-Type` and convert Windows-1251 or KOI8-R pages to UTF-8 before local searching. Wait at least three seconds between catalog requests, as required by `https://lib.ru/robots.txt`.

- Discovery and satellites: `https://lib.ru/What-s-new`, `https://lib.ru/HITPARAD/`, `https://samlib.ru/`, `https://music.lib.ru/`, `https://www.artlib.ru/`, `https://world.lib.ru/`, `https://turizm.lib.ru/`, `https://artofwar.ru/`, `https://okopka.ru/`.
- Author hubs: `https://lit.lib.ru/`, `https://fan.lib.ru/`, `https://det.lib.ru/`. Use the dedicated HTTP workflow above for classics at `az.lib.ru`.
- Prose and poetry: `/POEZIQ/`, `/PROZA/`, `/RUSSLIT/`, `/LITRA/`, `/SU/`, `/PXESY/`, `/NEWPROZA/`, `/INPROZ/`.
- Ancient literature: `/INOOLD/`, `/POEEAST/`, `/POECHIN/`.
- Children and adventure: `/TALES/`, `/PRIKL/`.
- Science fiction: `/RUFANT/`, `/INOFANT/`, `/TRANSLATION/`, `/SOCFANT/`, `/RAZNOE/`, `/SCIFICT/`, `/TRANSLATORS/`.
- History: `/HIST/`, `/INOSTRHIST/`, `/MEMUARY/`, `/HISTORY/`.
- Detective and law: `/RUSS_DETEKTIW/`, `/DETEKTIWY/`, `/PRAWO/`.
- Culture and humanities: `/CULTURE/`, `/FILOSOF/`, `/URIKOVA/SANTEM/`, `/URIKOVA/`, `/ASTROLOGY/`, `/RELIGION/`, `/DIALEKTIKA/`, `/POLITOLOG/`, `/PSIHO/`, `/NLP/`, `/DPEOPLE/`.
- Science and study: `/KIDS/`, `/NTL/`, `/DIC/`, `/TEXTBOOKS/`, `/NATUR/`, `/NTL/MED/`, `/BIBLIOGR/`, `/NTL/SPORT/`, `/ECONOMY/`.
- Computing: `/unixhelp/`, `/VMWARE/`, `/LINUXGUIDE/`, `/UNIXOID/`, `/WEBMASTER/`, `/SECURITY/`, `/TECHBOOKS/`, `/CTOTOR/`.
- Other topical catalogs: `/KSP/`, `/ALPINISM/`, `/PARACHUTE/`, `/EMIGRATION/`, `/ENGLISH/`, `/CINEMA/`, `/SONGS/`, `/ANEKDOTY/`.

Resolve paths beginning with `/` against `https://lib.ru`. The optional OPDS catalog at `http://lib.ru/opds/` can clarify catalog structure and EPUB/FB2 links, but it does not replace the required `GrepSearch` title lookup.

## Process a work

For a mechanical task, download the work instead of reading it into the model context:

```sh
tmpdir=$(mktemp -d)
trap 'rm -rf -- "$tmpdir"' EXIT
python3 "$SKILL_DIR/scripts/fetch_libru_text.py" "$work_url" "$tmpdir/book.txt"
```

The downloader accepts Lib.ru and its subdomains, prefers the plain-text `_Ascii.txt` representation for `.txt` works, extracts both ordinary preformatted pages and `az.lib.ru` classic pages, honors the declared legacy charset, and writes UTF-8 without overwriting an existing file.

Use local pipelines for counts, concordances, and frequency tables. For example, `rg -o '\p{L}+'`, `awk`, `sort`, and `uniq -c` are suitable for a simple word-frequency task; use a short Python program when Unicode tokenization or lemmatization needs more control. Never paste or read the entire work into the conversation for a mechanical calculation.

## Report results

Return up to five entries containing author or section, title, and direct URL. State when a link is an excerpt, translation, review, or external satellite page. If nothing is found, name the sources checked and suggest useful spelling variants. Do not reproduce long passages or full works.
