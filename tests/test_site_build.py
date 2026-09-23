import asyncio
import importlib.util
import os
from pathlib import Path

import pytest
from PIL import Image


SCRIPT_PATH = Path(__file__).parents[1] / "etc" / "site-build.py"
SPEC = importlib.util.spec_from_file_location("site_build", SCRIPT_PATH)
site_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site_build)


@pytest.mark.parametrize(
    "response",
    [
        "<!DOCTYPE html><html><body>Hello</body></html>",
        "```html\n<!DOCTYPE html><html><body>Hello</body></html>\n```",
        "Explanation\n<html><body>Hello</body></html>\nMore explanation",
    ],
)
def test_extract_html(response):
    result = site_build.extract_html(response)
    assert result.lower().endswith("</html>")
    assert "Hello" in result


def test_extract_html_rejects_incomplete_response():
    with pytest.raises(ValueError, match="complete HTML document"):
        site_build.extract_html("<html><body>Missing closing tag")


def test_make_input_adds_all_images():
    result = site_build.make_input(
        "Compare these images",
        site_build.REFERENCE_PATH,
        site_build.REFERENCE_PATH,
    )

    content = result[0]["content"]
    assert content[0] == {"type": "input_text", "text": "Compare these images"}
    assert [item["type"] for item in content[1:]] == ["input_image", "input_image"]


@pytest.mark.skipif(
    not os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"),
    reason="Set PLAYWRIGHT_CHROMIUM_EXECUTABLE to run the browser smoke test.",
)
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_render_html_uses_exact_viewport_size(tmp_path):
    output_path = tmp_path / "render.png"
    old_policy = asyncio.get_event_loop_policy()
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        site_build.render_html(
            "<!DOCTYPE html><html><body>Smoke test</body></html>",
            output_path,
            1398,
            956,
        )
    finally:
        asyncio.set_event_loop_policy(old_policy)

    with Image.open(output_path) as rendered:
        assert rendered.size == (1398, 956)


def test_loop_passes_html_and_feedback_to_next_iteration(tmp_path, monkeypatch):
    generation_calls = []
    critiques = iter(
        [
            site_build.SiteCritique(score=20, recommendations=["Move the search box"]),
            site_build.SiteCritique(score=95, recommendations=[]),
        ]
    )

    def fake_generate(reference_path, previous_html=None, feedback=None):
        generation_calls.append((previous_html, feedback))
        return f"<!DOCTYPE html><html><body>{len(generation_calls)}</body></html>"

    def fake_render(html_code, output_path, width, height):
        Image.new("RGB", (width, height), "white").save(output_path)
        return output_path

    monkeypatch.setattr(site_build, "SITE_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(site_build, "generate_html", fake_generate)
    monkeypatch.setattr(site_build, "render_html", fake_render)
    monkeypatch.setattr(site_build, "critique_images", lambda *args: next(critiques))

    history = site_build.run_site_build(threshold=90, max_iterations=5)

    assert len(history) == 2
    assert generation_calls[0] == (None, None)
    assert "<body>1</body>" in generation_calls[1][0]
    assert generation_calls[1][1].score == 20
    assert (tmp_path / "01.html").is_file()
    assert (tmp_path / "01.png").is_file()
    assert (tmp_path / "02.html").is_file()
    assert (tmp_path / "02.png").is_file()


def test_loop_stops_at_iteration_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(site_build, "SITE_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        site_build,
        "generate_html",
        lambda *args: "<!DOCTYPE html><html><body>Test</body></html>",
    )

    def fake_render(html_code, output_path, width, height):
        Image.new("RGB", (width, height), "white").save(output_path)
        return output_path

    monkeypatch.setattr(site_build, "render_html", fake_render)
    monkeypatch.setattr(
        site_build,
        "critique_images",
        lambda *args: site_build.SiteCritique(score=10, recommendations=["Keep going"]),
    )

    history = site_build.run_site_build(threshold=90, max_iterations=2)

    assert len(history) == 2
