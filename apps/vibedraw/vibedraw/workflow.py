from __future__ import annotations

import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

from rich.console import Console

from .config import AppConfig
from .models import IterationRecord, RunContext
from .services import EvaluationParseError, ImageServices


class AgenticImageWorkflow:
    def __init__(
        self,
        services: ImageServices,
        config: AppConfig,
        console: Console | None = None,
    ):
        self.services = services
        self.config = config
        self.console = console or Console()

    @staticmethod
    def validate_concept(concept: str) -> str:
        clean = " ".join((concept or "").split())
        if not clean:
            raise ValueError("Enter or select an abstract concept first.")
        if len(clean) > 200:
            raise ValueError("Keep the concept to 200 characters or fewer.")
        return clean

    def run(self, concept: str) -> Iterator[RunContext]:
        concept = self.validate_concept(concept)
        work_dir = Path(tempfile.mkdtemp(prefix="vibedraw_"))
        context = RunContext(
            concept=concept,
            run_id=uuid.uuid4().hex,
            work_dir=str(work_dir),
            status=f'Preparing the first visual metaphor for “{concept}”.',
        )

        previous_prompt: str | None = None
        previous_evaluation = None

        for iteration in range(1, self.config.max_iterations + 1):
            try:
                if previous_prompt is None:
                    prompt = self.services.create_initial_prompt(concept)
                    prompt_kind = "initial"
                else:
                    prompt = self.services.refine_prompt(
                        concept, previous_prompt, previous_evaluation
                    )
                    prompt_kind = "refined"

                record = IterationRecord(
                    iteration=iteration,
                    prompt=prompt,
                    prompt_kind=prompt_kind,
                )
                context.iterations.append(record)
                context.status = f"Iteration {iteration}: prompt ready; generating image."
                self.console.rule(f"Iteration {iteration} · {concept}")
                self.console.print("Prompt", style="bold blue" if iteration == 1 else "bold magenta")
                self.console.print(prompt)
                yield context

                image = self.services.generate_image(prompt)
                image_path = work_dir / f"iteration_{iteration:02d}.png"
                image.save(image_path, format="PNG")
                record.image_path = str(image_path)
                context.status = f"Iteration {iteration}: image ready; asking the VLM to evaluate it."
                self.console.print(f"Image saved: {image_path}", style="cyan")
                yield context

                try:
                    evaluation = self.services.evaluate_image(concept, image)
                except EvaluationParseError:
                    self.console.print(
                        "Structured evaluation was malformed; retrying once.",
                        style="yellow",
                    )
                    evaluation = self.services.evaluate_image(concept, image)

                record.evaluation = evaluation
                context.update_best(record)
                self.console.print(
                    f"Fit: {evaluation.fit_percent:.1f}%",
                    style="bold green" if evaluation.fit_percent >= self.config.threshold else "bold yellow",
                )
                if evaluation.strengths:
                    self.console.print("Strengths", style="green")
                    for item in evaluation.strengths:
                        self.console.print(f"  • {item}")
                if evaluation.recommendations:
                    self.console.print("Recommendations", style="yellow")
                    for item in evaluation.recommendations:
                        self.console.print(f"  • {item}")

                if evaluation.fit_percent >= self.config.threshold:
                    context.stop_reason = "threshold_met"
                    context.status = (
                        f"Target met at iteration {iteration}: "
                        f"{evaluation.fit_percent:.1f}% concept fit."
                    )
                    yield context
                    return

                previous_prompt = prompt
                previous_evaluation = evaluation
                context.status = (
                    f"Iteration {iteration}: {evaluation.fit_percent:.1f}% fit; "
                    "refining the prompt."
                )
                yield context

            except Exception as exc:
                if context.current is not None:
                    context.current.error = f"{type(exc).__name__}: {exc}"
                context.error = str(exc)
                context.stop_reason = "error"
                context.status = f"Run stopped after an error: {exc}"
                self.console.print(context.status, style="bold red")
                yield context
                return

        context.stop_reason = "iteration_limit"
        best = context.best_score
        best_text = f" Best result: {best:.1f}%." if best is not None else ""
        context.status = f"Iteration limit reached before 98%.{best_text}"
        yield context

