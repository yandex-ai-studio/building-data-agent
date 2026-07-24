from __future__ import annotations

from PIL import Image
from pydantic import SecretStr, ValidationError

from vibedraw.config import AppConfig
from vibedraw.models import ConceptEvaluation
from vibedraw.workflow import AgenticImageWorkflow


class FakeServices:
    def __init__(self, scores, *, evaluation_error=None):
        self.scores = iter(scores)
        self.evaluation_error = evaluation_error
        self.generate_calls = 0
        self.refine_calls = []

    def create_initial_prompt(self, concept):
        return f"initial prompt for {concept}"

    def refine_prompt(self, concept, previous_prompt, evaluation):
        self.refine_calls.append((concept, previous_prompt, evaluation))
        return f"refined prompt {len(self.refine_calls)} for {concept}"

    def generate_image(self, prompt):
        self.generate_calls += 1
        return Image.new("RGB", (32, 24), (self.generate_calls * 20, 40, 80))

    def evaluate_image(self, concept, image):
        if self.evaluation_error:
            raise self.evaluation_error
        score = next(self.scores)
        return ConceptEvaluation(
            fit_percent=score,
            strengths=["clear focal point"],
            recommendations=[] if score >= 98 else ["make the metaphor clearer"],
        )


def config(**overrides):
    values = {
        "folder_id": "folder",
        "api_key": SecretStr("secret"),
        "max_iterations": 5,
        "threshold": 98,
    }
    values.update(overrides)
    return AppConfig(**values)


def final_context(workflow, concept="happiness"):
    return list(workflow.run(concept))[-1]


def test_stops_immediately_at_threshold():
    services = FakeServices([98])
    result = final_context(AgenticImageWorkflow(services, config()))
    assert result.stop_reason == "threshold_met"
    assert len(result.iterations) == 1
    assert services.generate_calls == 1


def test_runs_exactly_five_iterations_without_threshold():
    services = FakeServices([50, 60, 70, 80, 90])
    result = final_context(AgenticImageWorkflow(services, config()))
    assert result.stop_reason == "iteration_limit"
    assert len(result.iterations) == 5
    assert services.generate_calls == 5


def test_refinement_receives_complete_previous_prompt_and_feedback():
    services = FakeServices([70, 98])
    result = final_context(AgenticImageWorkflow(services, config()))
    assert result.stop_reason == "threshold_met"
    concept, previous_prompt, evaluation = services.refine_calls[0]
    assert concept == "happiness"
    assert previous_prompt == "initial prompt for happiness"
    assert evaluation.recommendations == ["make the metaphor clearer"]


def test_best_iteration_survives_score_regression():
    services = FakeServices([70, 94, 75, 80, 82])
    result = final_context(AgenticImageWorkflow(services, config()))
    assert result.best_iteration == 2
    assert result.best_score == 94


def test_fit_percent_is_bounded():
    try:
        ConceptEvaluation(fit_percent=101, strengths=[], recommendations=[])
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected out-of-range score to fail validation")


def test_rejects_empty_and_long_concepts_before_api_calls():
    services = FakeServices([98])
    workflow = AgenticImageWorkflow(services, config())
    for invalid in ["   ", "x" * 201]:
        try:
            list(workflow.run(invalid))
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid concept to fail")
    assert services.generate_calls == 0


def test_partial_image_history_survives_evaluation_failure():
    services = FakeServices([], evaluation_error=RuntimeError("vlm unavailable"))
    result = final_context(AgenticImageWorkflow(services, config()))
    assert result.stop_reason == "error"
    assert result.iterations[0].image_path is not None
    assert result.iterations[0].error == "RuntimeError: vlm unavailable"

