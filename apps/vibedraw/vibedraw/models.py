from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ConceptEvaluation(BaseModel):
    fit_percent: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


@dataclass
class IterationRecord:
    iteration: int
    prompt: str
    prompt_kind: Literal["initial", "refined"]
    image_path: str | None = None
    evaluation: ConceptEvaluation | None = None
    error: str | None = None

    def manifest(self) -> dict:
        data = asdict(self)
        data["image_filename"] = Path(self.image_path).name if self.image_path else None
        data.pop("image_path", None)
        if self.evaluation is not None:
            data["evaluation"] = self.evaluation.model_dump()
        return data


@dataclass
class RunContext:
    concept: str = ""
    run_id: str = ""
    work_dir: str = ""
    iterations: list[IterationRecord] = field(default_factory=list)
    status: str = "Ready for a concept."
    stop_reason: str | None = None
    best_iteration: int | None = None
    error: str | None = None

    @property
    def current(self) -> IterationRecord | None:
        return self.iterations[-1] if self.iterations else None

    @property
    def best(self) -> IterationRecord | None:
        if self.best_iteration is None:
            return None
        return next(
            (item for item in self.iterations if item.iteration == self.best_iteration),
            None,
        )

    @property
    def best_score(self) -> float | None:
        best = self.best
        return best.evaluation.fit_percent if best and best.evaluation else None

    def update_best(self, record: IterationRecord) -> None:
        if record.evaluation is None:
            return
        if self.best_score is None or record.evaluation.fit_percent > self.best_score:
            self.best_iteration = record.iteration

