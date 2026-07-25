from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from agents import Agent, StopAtTools, WebSearchTool, function_tool, handoff


# =============================================================================
# SHARED STATE
# =============================================================================

SOURCE_LIMIT = 30

_context: Any = None
_root = Path.cwd()
_topic = ""
_concepts: list[dict[str, str]] = []
_links: list[dict[str, str]] = []


# =============================================================================
# SMALL HELPERS
# =============================================================================

def normalize_slug(value: str) -> str:
    slug = unicodedata.normalize("NFKC", value.strip()).casefold()
    slug = re.sub(r"\s+", "-", slug)
    allowed = all(character == "-" or character.isalnum() for character in slug)
    reserved = {"graph", "readme", "con", "prn", "aux", "nul"}
    if not slug or not allowed or len(slug) > 48 or len(slug.split("-")) > 5 or slug in reserved:
        raise ValueError("Use a unique 1-5 word Unicode slug with letters, numbers, and hyphens.")
    return slug


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def source_notes() -> list[Any]:
    return _context.notes_store.list_notes(category="source")


def source_count() -> int:
    return len(source_notes())


def pending_todos() -> list[Any]:
    return [item for item in _context.todo_store.items if not item.done]


def find_concept(slug: str) -> dict[str, str] | None:
    return next((concept for concept in _concepts if concept["id"] == slug), None)


def reset_wiki(topic: str) -> None:
    global _topic
    _context.notes_store.clear()
    _context.todo_store.clear()
    _topic = topic.strip()
    _concepts.clear()
    _links.clear()


# =============================================================================
# RESEARCH TOOLS
# =============================================================================

@function_tool
def start_wiki(topic: str) -> str:
    """Clear previous wiki-building state and remember the new topic."""
    reset_wiki(topic)
    return f"Started a fresh wiki build for: {_topic}"


def save_source(title: str, url: str, summary: str) -> str:
    normalized_url = normalize_url(url)
    if any(note.url == normalized_url for note in source_notes()):
        return f"Source already recorded: {normalized_url}"
    if source_count() >= SOURCE_LIMIT:
        return f"Source limit reached ({SOURCE_LIMIT}). Stop research and hand off."

    _context.notes_store.create_note(
        category="source",
        title=title.strip(),
        body=summary.strip(),
        url=normalized_url,
    )
    count = source_count()
    suffix = " Stop research and hand off." if count == SOURCE_LIMIT else ""
    return f"Recorded source {count}/{SOURCE_LIMIT}: {title.strip()}.{suffix}"


@function_tool
def record_source(title: str, url: str, summary: str) -> str:
    """Record one studied web source with its URL and extended Markdown summary."""
    return save_source(title, url, summary)


def research_status_text() -> str:
    lines = [f"Sources: {source_count()}/{SOURCE_LIMIT}", "TODOs:"]
    for index, item in enumerate(_context.todo_store.items):
        state = "done" if item.done else "pending"
        lines.append(f"- {index}: [{state}] {item.title}")
    if not _context.todo_store.items:
        lines.append("- No TODO items.")
    ready = source_count() > 0 and (source_count() == SOURCE_LIMIT or not pending_todos())
    lines.append(f"Ready for conceptualization: {'yes' if ready else 'no'}")
    return "\n".join(lines)


@function_tool
def research_status() -> str:
    """Show source count, every numbered TODO, and whether research may finish."""
    return research_status_text()


def source_notes_text(offset: int = 0, limit: int = 10) -> str:
    notes = source_notes()
    page = notes[offset : offset + limit]
    blocks = [f"Source notes {offset + 1}-{offset + len(page)} of {len(notes)}"]
    for index, note in enumerate(page, offset + 1):
        blocks.append(f"## {index}. {note.title}\nURL: {note.url}\n\n{note.body}")
    return "\n\n".join(blocks)


@function_tool
def list_source_notes(offset: int = 0, limit: int = 10) -> str:
    """Read a page of researched source notes; use successive offsets to read all notes."""
    return source_notes_text(offset, limit)


# =============================================================================
# CONCEPT GRAPH TOOLS
# =============================================================================

def save_concept(slug: str, name: str, description: str) -> str:
    slug = normalize_slug(slug)
    concept = find_concept(slug)
    if concept and concept["name"].casefold() != name.strip().casefold():
        raise ValueError(f"Slug '{slug}' already belongs to '{concept['name']}'.")

    value = {"id": slug, "name": name.strip(), "description": description.strip()}
    if concept:
        concept.update(value)
        return f"Updated concept '{name}' ({slug})."
    _concepts.append(value)
    return f"Created concept '{name}' ({slug})."


@function_tool
def upsert_concept(slug: str, name: str, description: str) -> str:
    """Create or update a concept using a short semantic Unicode slug."""
    return save_concept(slug, name, description)


def save_link(source: str, target: str, relation: str, description: str) -> str:
    source = normalize_slug(source)
    target = normalize_slug(target)
    if not find_concept(source) or not find_concept(target):
        raise ValueError("Create both endpoint concepts before linking them.")

    existing = next(
        (
            link
            for link in _links
            if link["source"] == source
            and link["target"] == target
            and link["relation"].casefold() == relation.strip().casefold()
        ),
        None,
    )
    value = {
        "source": source,
        "target": target,
        "relation": relation.strip(),
        "description": description.strip(),
    }
    if existing:
        existing.update(value)
        return f"Updated link {source} -[{relation}]-> {target}."
    _links.append(value)
    return f"Created link {source} -[{relation}]-> {target}."


@function_tool
def upsert_link(source: str, target: str, relation: str, description: str) -> str:
    """Create or update a directed relation between two existing concept slugs."""
    return save_link(source, target, relation, description)


def merge_graph_concepts(
    slugs: list[str],
    target_slug: str,
    name: str,
    description: str,
) -> str:
    source_slugs = {normalize_slug(slug) for slug in slugs}
    target_slug = normalize_slug(target_slug)

    _concepts[:] = [concept for concept in _concepts if concept["id"] not in source_slugs]
    _concepts.append({"id": target_slug, "name": name.strip(), "description": description.strip()})

    merged_links: list[dict[str, str]] = []
    for link in _links:
        value = dict(link)
        if value["source"] in source_slugs:
            value["source"] = target_slug
        if value["target"] in source_slugs:
            value["target"] = target_slug
        key = (value["source"], value["target"], value["relation"].casefold())
        if value["source"] != value["target"] and not any(
            (item["source"], item["target"], item["relation"].casefold()) == key
            for item in merged_links
        ):
            merged_links.append(value)
    _links[:] = merged_links
    return f"Merged {len(source_slugs)} concepts into '{name}' ({target_slug})."


@function_tool
def merge_concepts(
    slugs: list[str],
    target_slug: str,
    name: str,
    description: str,
) -> str:
    """Merge duplicate concepts and rewire their links to one target concept."""
    return merge_graph_concepts(slugs, target_slug, name, description)


def graph_data() -> dict[str, Any]:
    return {
        "topic": _topic,
        "vertices": sorted(_concepts, key=lambda concept: concept["name"].casefold()),
        "links": sorted(
            _links,
            key=lambda link: (link["source"], link["target"], link["relation"].casefold()),
        ),
    }


@function_tool
def inspect_graph() -> str:
    """Return the complete current concept graph as formatted JSON."""
    return json.dumps(graph_data(), ensure_ascii=False, indent=2)


# =============================================================================
# WIKI EXPORT
# =============================================================================

def write_wiki() -> str:
    if not _concepts:
        raise ValueError("Cannot export an empty concept graph.")

    output = _root / "wiki"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()

    (output / "graph.json").write_text(
        json.dumps(graph_data(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    index = [f"# {_topic}", "", "## Concepts", ""]
    for concept in graph_data()["vertices"]:
        index.append(f"- [{concept['name']}]({concept['id']}.md)")
    (output / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    for concept in _concepts:
        outgoing = [link for link in _links if link["source"] == concept["id"]]
        incoming = [link for link in _links if link["target"] == concept["id"]]
        lines = [f"# {concept['name']}", "", concept["description"], "", "## Outgoing links", ""]
        for link in outgoing:
            target = find_concept(link["target"])
            lines.append(
                f"- [{target['name']}]({target['id']}.md) — "
                f"**{link['relation']}**: {link['description']}"
            )
        if not outgoing:
            lines.append("No outgoing links.")

        lines.extend(["", "## Incoming links", ""])
        for link in incoming:
            source = find_concept(link["source"])
            lines.append(
                f"- [{source['name']}]({source['id']}.md) — "
                f"**{link['relation']}**: {link['description']}"
            )
        if not incoming:
            lines.append("No incoming links.")
        (output / f"{concept['id']}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return (
        f"Exported wiki to {output} from {source_count()} sources: "
        f"{len(_concepts)} concepts and {len(_links)} links."
    )


@function_tool
def export_wiki() -> str:
    """Replace the generated wiki directory with the current concept graph."""
    return write_wiki()


# =============================================================================
# AGENTS AND HANDOFFS
# =============================================================================

def start_research(_run_context: Any) -> None:
    _context.log(f"Wiki research started: {_topic}")


def start_conceptualization(_run_context: Any) -> None:
    if source_count() == 0:
        raise ValueError("Research needs at least one source.")
    if source_count() < SOURCE_LIMIT and pending_todos():
        raise ValueError("Research still has unfinished TODOs.")
    _context.log(f"Research complete with {source_count()} sources. Building concept graph.")


CONCEPTUALIZER_INSTRUCTIONS = """
You are the Conceptualizer in a wiki-building pipeline.

1. Read every source note with list_source_notes, using offsets 0, 10, and 20 as needed.
2. Identify important concepts and relations across all notes.
3. Combine aliases and near-duplicates. Invent useful super-concepts when needed.
4. Create every node with upsert_concept. Use a short lowercase Unicode kebab-case slug in the
   concept's own script, normally 1-5 words and never an opaque number or hash.
5. Write Markdown descriptions with inline links to supporting researched sources.
6. Create directed links with short, consistent relation names.
7. Inspect the graph, fix problems, then call export_wiki exactly once as your final action.

An article and a paper about the same idea can support one concept. Paper and Book can both be
a-kind-of an invented Publication concept.
""".strip()


conceptualizer = Agent(
    name="WikiConceptualizer",
    handoff_description="Builds and exports a concept graph from completed research notes.",
    instructions=CONCEPTUALIZER_INSTRUCTIONS,
    tools=[list_source_notes, upsert_concept, upsert_link, merge_concepts, inspect_graph, export_wiki],
    tool_use_behavior=StopAtTools(stop_at_tool_names=["export_wiki"]),
)


conceptualizer_handoff = handoff(
    agent=conceptualizer,
    on_handoff=start_conceptualization,
    tool_name_override="finish_research_and_build_graph",
    tool_description_override="Hand off only when research_status says conceptualization is ready.",
)


RESEARCHER_INSTRUCTIONS = """
You are the Researcher in a wiki-building pipeline.

1. Create 3-5 TODO questions covering the topic from several useful angles.
2. Work through TODOs with web search and prefer authoritative sources.
3. For each studied source, record its title, URL, and an extended Markdown summary with record_source.
4. Add useful newly discovered concepts, questions, and links as TODOs. Avoid duplicates.
5. Mark TODOs done after their useful sources are recorded. Call research_status regularly.
6. Stop when all TODOs are done or 30 unique sources are recorded.
7. When research_status says ready, call finish_research_and_build_graph.

If no source can be recorded, explain the failure instead of handing off.
""".strip()


researcher = Agent(
    name="WikiResearcher",
    handoff_description="Researches a topic with web search, notes, and a TODO queue.",
    instructions=RESEARCHER_INSTRUCTIONS,
    tools=[WebSearchTool(), record_source, research_status],
    handoffs=[conceptualizer_handoff],
)


research_handoff = handoff(
    agent=researcher,
    on_handoff=start_research,
    tool_name_override="start_wiki_research",
    tool_description_override="Hand off after the start_wiki tool has stored the topic.",
)


agent = Agent(
    name="WikiBuilder",
    instructions="""
For a non-empty topic, first call start_wiki with a concise topic, then call start_wiki_research.
Do not research or build concepts yourself. If the user did not provide a meaningful topic, ask for one.
""".strip(),
    tools=[start_wiki],
    handoffs=[research_handoff],
)


# =============================================================================
# MA HOST INTEGRATION
# =============================================================================

def set_context(context: Any) -> None:
    global _context, _root
    _context = context
    _root = Path.cwd()

    researcher.tools = [WebSearchTool(), record_source, research_status, *context.todo_tools]
    agent.tools = [start_wiki, *context.clarification_tools]


def get_props() -> dict:
    return {
        "display_name": "Wiki Builder",
        "uses_notes": True,
        "uses_todo": True,
        "max_turns": 120,
    }
