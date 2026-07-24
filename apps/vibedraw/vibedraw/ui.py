from __future__ import annotations

import html
from collections.abc import Callable, Iterator

import gradio as gr

from .artifacts import build_archive, cleanup_context
from .config import AppConfig, load_config
from .models import RunContext
from .services import AIStudioServices, ImageServices
from .workflow import AgenticImageWorkflow


CONCEPTS = [
    "happiness",
    "despair",
    "loneliness",
    "hope",
    "freedom",
    "harmony",
    "chaos",
    "nostalgia",
    "courage",
    "tenderness",
    "wonder",
    "resilience",
]


CSS = """
:root {
  --bg: oklch(1 0 0);
  --surface: oklch(0.965 0.006 258);
  --ink: oklch(0.19 0.02 258);
  --muted: oklch(0.46 0.025 258);
  --primary: oklch(0.52 0.17 258);
  --accent: oklch(0.70 0.15 70);
  --prompt: oklch(0.95 0.028 258);
  --refine: oklch(0.95 0.035 305);
  --evaluation: oklch(0.95 0.035 155);
  --recommendation: oklch(0.95 0.045 70);
  --danger: oklch(0.94 0.035 25);
}

body, .gradio-container {
  background: var(--bg) !important;
  color: var(--ink) !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

.gradio-container {
  max-width: 1460px !important;
  padding: 24px 28px 40px !important;
}

#vibedraw-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 28px;
  padding: 4px 2px 22px;
}

.brand-lockup h1 {
  color: var(--ink);
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.025em;
  margin: 0 0 8px;
}

.brand-lockup p {
  color: var(--muted);
  font-size: 15px;
  line-height: 1.55;
  margin: 0;
  max-width: 68ch;
}

.contract-strip {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.contract-strip span {
  background: var(--surface);
  border-radius: 999px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 650;
  padding: 7px 10px;
  white-space: nowrap;
}

#composer {
  background: var(--surface);
  border-radius: 16px;
  padding: 18px;
}

#composer textarea, #composer input {
  color: var(--ink) !important;
}

#composer textarea::placeholder, #composer input::placeholder {
  color: oklch(0.39 0.025 258) !important;
  opacity: 1 !important;
}

#generate-btn button {
  background: var(--primary) !important;
  color: white !important;
}

#generate-btn button:hover {
  background: oklch(0.46 0.17 258) !important;
}

button:focus-visible, textarea:focus-visible, input:focus-visible {
  outline: 3px solid oklch(0.72 0.13 258) !important;
  outline-offset: 2px !important;
}

#run-status {
  margin: 14px 0;
}

.status-line {
  align-items: center;
  background: var(--surface);
  border-radius: 12px;
  color: var(--ink);
  display: flex;
  font-size: 14px;
  gap: 10px;
  min-height: 44px;
  padding: 10px 14px;
}

.status-dot {
  background: var(--primary);
  border-radius: 999px;
  flex: 0 0 auto;
  height: 9px;
  width: 9px;
}

.status-line.success .status-dot { background: oklch(0.50 0.14 155); }
.status-line.warning .status-dot { background: oklch(0.60 0.15 70); }
.status-line.error .status-dot { background: oklch(0.49 0.18 25); }

#workspace {
  align-items: stretch;
  gap: 18px;
}

#process-panel, #light-table {
  min-height: 620px;
}

#process-panel {
  background: var(--surface);
  border-radius: 16px;
  padding: 18px;
}

.panel-heading {
  color: var(--ink);
  font-size: 17px;
  font-weight: 700;
  margin: 0 0 12px;
}

.trace-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 552px;
  overflow-y: auto;
  padding-right: 4px;
}

.trace-empty {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
  max-width: 52ch;
  padding: 18px 2px;
}

.trace-entry {
  border-radius: 12px;
  color: var(--ink);
  padding: 13px 14px;
}

.trace-entry.initial { background: var(--prompt); }
.trace-entry.refined { background: var(--refine); }
.trace-entry.evaluation { background: var(--evaluation); }
.trace-entry.recommendation { background: var(--recommendation); }
.trace-entry.error { background: var(--danger); }

.trace-label {
  display: block;
  font-size: 12px;
  font-weight: 750;
  margin-bottom: 7px;
}

.trace-entry pre {
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.trace-entry ul {
  margin: 6px 0 0 18px;
  padding: 0;
}

.trace-entry li {
  font-size: 13px;
  line-height: 1.5;
  margin: 3px 0;
}

#light-table {
  background: oklch(0.985 0.003 258);
  border-radius: 16px;
  padding: 18px;
}

.score-panel {
  color: var(--ink);
  margin-bottom: 12px;
}

.score-row {
  align-items: baseline;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.score-title { font-size: 14px; font-weight: 700; }
.score-value { font-size: 18px; font-weight: 750; }
.score-caption { color: var(--muted); font-size: 12px; margin-top: 7px; }

.score-track {
  background: oklch(0.90 0.012 258);
  border-radius: 999px;
  height: 8px;
  overflow: hidden;
}

.score-fill {
  background: var(--primary);
  border-radius: inherit;
  height: 100%;
  transition: width 180ms ease-out;
}

#current-image {
  background: white;
  border-radius: 12px;
  min-height: 500px;
  overflow: hidden;
}

#current-image img { object-fit: contain !important; }

#gallery-section {
  margin-top: 22px;
}

#iteration-gallery {
  background: var(--surface);
  border-radius: 16px;
  padding: 12px;
}

@media (max-width: 900px) {
  .gradio-container { padding: 18px 16px 32px !important; }
  #vibedraw-header { align-items: flex-start; flex-direction: column; }
  .contract-strip { justify-content: flex-start; }
  #workspace { flex-direction: column; }
  #process-panel, #light-table { min-height: auto; }
  .trace-stack { max-height: 480px; }
  #current-image { min-height: 360px; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
"""


HEADER_HTML = """
<header id="vibedraw-header">
  <div class="brand-lockup">
    <h1>VibeDraw</h1>
    <p>Watch three models turn an abstract idea into a clearer image, one visible decision at a time.</p>
  </div>
  <div class="contract-strip" aria-label="Workflow settings">
    <span>98% target</span>
    <span>5 iterations max</span>
    <span>LLM → YandexART → VLM</span>
  </div>
</header>
"""


def _list_html(items: list[str]) -> str:
    if not items:
        return "<p>None recorded.</p>"
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def render_trace(context: RunContext) -> str:
    if not context.iterations:
        return """
<div class="trace-stack">
  <div class="trace-empty">
    Choose a concept and generate. The initial prompt appears here first; each image is then scored and, when needed, followed by a visibly revised prompt.
  </div>
</div>
"""

    parts = ['<div class="trace-stack">']
    for record in context.iterations:
        prompt_label = "Initial prompt" if record.prompt_kind == "initial" else "Refined prompt"
        parts.append(
            f'<section class="trace-entry {record.prompt_kind}">'
            f'<span class="trace-label">Iteration {record.iteration} · {prompt_label}</span>'
            f'<pre>{html.escape(record.prompt)}</pre></section>'
        )
        if record.evaluation is not None:
            score = record.evaluation.fit_percent
            parts.append(
                '<section class="trace-entry evaluation">'
                f'<span class="trace-label">Iteration {record.iteration} · Evaluation · {score:.1f}%</span>'
                f'{_list_html(record.evaluation.strengths)}</section>'
            )
            if record.evaluation.recommendations:
                parts.append(
                    '<section class="trace-entry recommendation">'
                    f'<span class="trace-label">Iteration {record.iteration} · Recommendations</span>'
                    f'{_list_html(record.evaluation.recommendations)}</section>'
                )
        if record.error:
            parts.append(
                '<section class="trace-entry error">'
                f'<span class="trace-label">Iteration {record.iteration} · Error</span>'
                f'<pre>{html.escape(record.error)}</pre></section>'
            )
    if context.error and not any(item.error for item in context.iterations):
        parts.append(
            '<section class="trace-entry error"><span class="trace-label">Run error</span>'
            f'<pre>{html.escape(context.error)}</pre></section>'
        )
    parts.append("</div>")
    return "".join(parts)


def render_score(context: RunContext) -> str:
    current = context.current
    score = current.evaluation.fit_percent if current and current.evaluation else None
    best = context.best_score
    width = min(max(score or 0, 0), 100)
    value = f"{score:.1f}%" if score is not None else "Awaiting evaluation"
    best_text = f"Best so far: {best:.1f}%" if best is not None else "Target: 98% concept fit"
    return f"""
<div class="score-panel">
  <div class="score-row">
    <span class="score-title">Current concept fit</span>
    <span class="score-value">{html.escape(value)}</span>
  </div>
  <div class="score-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{width:.1f}">
    <div class="score-fill" style="width:{width:.1f}%"></div>
  </div>
  <div class="score-caption">{html.escape(best_text)}</div>
</div>
"""


def render_status(context: RunContext) -> str:
    style = ""
    if context.stop_reason == "threshold_met":
        style = "success"
    elif context.stop_reason in {"iteration_limit", "stopped"}:
        style = "warning"
    elif context.stop_reason == "error":
        style = "error"
    return (
        f'<div class="status-line {style}" role="status" aria-live="polite">'
        f'<span class="status-dot" aria-hidden="true"></span>'
        f'<span>{html.escape(context.status)}</span></div>'
    )


def gallery_items(context: RunContext) -> list[tuple[str, str]]:
    result = []
    for record in context.iterations:
        if not record.image_path:
            continue
        score = (
            f"{record.evaluation.fit_percent:.1f}%"
            if record.evaluation is not None
            else "evaluating"
        )
        best = " · best" if record.iteration == context.best_iteration else ""
        result.append((record.image_path, f"Iteration {record.iteration} · {score}{best}"))
    return result


def ui_payload(context: RunContext, config: AppConfig):
    current_path = context.current.image_path if context.current else None
    archive = build_archive(context, config) if any(i.image_path for i in context.iterations) else None
    return (
        current_path,
        gallery_items(context),
        render_trace(context),
        render_score(context),
        render_status(context),
        context,
        archive,
    )


def build_demo(
    *,
    config: AppConfig | None = None,
    service_factory: Callable[[AppConfig], ImageServices] = AIStudioServices,
) -> gr.Blocks:
    def run_concept(concept: str, previous: RunContext | None) -> Iterator[tuple]:
        try:
            clean = AgenticImageWorkflow.validate_concept(concept)
            active_config = config or load_config()
        except Exception as exc:
            context = previous or RunContext()
            context.error = str(exc)
            context.stop_reason = "error"
            context.status = str(exc)
            yield (
                context.current.image_path if context.current else None,
                gallery_items(context),
                render_trace(context),
                render_score(context),
                render_status(context),
                context,
                None,
            )
            return

        cleanup_context(previous)
        workflow = AgenticImageWorkflow(service_factory(active_config), active_config)
        for context in workflow.run(clean):
            yield ui_payload(context, active_config)

    def stop_run(context: RunContext | None):
        context = context or RunContext()
        context.stop_reason = "stopped"
        context.status = "Stop requested. The current API call may finish before the run halts."
        active_config = config or load_config()
        archive = build_archive(context, active_config)
        return render_trace(context), render_score(context), render_status(context), context, archive

    def clear_run(context: RunContext | None):
        cleanup_context(context)
        empty = RunContext()
        return None, [], render_trace(empty), render_score(empty), render_status(empty), empty, None

    with gr.Blocks(title="VibeDraw") as demo:
        run_state = gr.State(value=lambda: RunContext(), delete_callback=cleanup_context)
        gr.HTML(HEADER_HTML)

        with gr.Column(elem_id="composer"):
            concept = gr.Textbox(
                label="Abstract concept",
                placeholder="Type a concept such as belonging, stillness, or renewal…",
                max_lines=2,
                autofocus=True,
            )
            gr.Examples(
                examples=[[item] for item in CONCEPTS],
                inputs=[concept],
                label="Try a concept",
                cache_examples=False,
            )
            with gr.Row():
                generate = gr.Button("Generate and refine", variant="primary", elem_id="generate-btn")
                stop = gr.Button("Stop", variant="stop")
                clear = gr.Button("Clear", variant="secondary")
                download = gr.DownloadButton("Download run", value=None, variant="secondary")

        status = gr.HTML(render_status(RunContext()), elem_id="run-status")

        with gr.Row(elem_id="workspace"):
            with gr.Column(scale=5, elem_id="process-panel"):
                gr.HTML('<h2 class="panel-heading">Agent process</h2>')
                trace = gr.HTML(render_trace(RunContext()))
            with gr.Column(scale=7, elem_id="light-table"):
                score = gr.HTML(render_score(RunContext()))
                current_image = gr.Image(
                    label="Current image",
                    interactive=False,
                    type="filepath",
                    height=510,
                    elem_id="current-image",
                )

        with gr.Column(elem_id="gallery-section"):
            gr.HTML('<h2 class="panel-heading">Iteration history</h2>')
            gallery = gr.Gallery(
                label=None,
                columns=5,
                rows=1,
                height=250,
                object_fit="contain",
                allow_preview=True,
                buttons=["download", "download_all", "fullscreen"],
                interactive=False,
                elem_id="iteration-gallery",
            )

        outputs = [current_image, gallery, trace, score, status, run_state, download]
        run_event = generate.click(
            fn=run_concept,
            inputs=[concept, run_state],
            outputs=outputs,
            concurrency_limit=1,
            trigger_mode="once",
        )
        submit_event = concept.submit(
            fn=run_concept,
            inputs=[concept, run_state],
            outputs=outputs,
            concurrency_limit=1,
            trigger_mode="once",
        )
        stop.click(
            fn=stop_run,
            inputs=[run_state],
            outputs=[trace, score, status, run_state, download],
            cancels=[run_event, submit_event],
        )
        clear.click(
            fn=clear_run,
            inputs=[run_state],
            outputs=outputs,
            cancels=[run_event, submit_event],
        )

    return demo
