from __future__ import annotations

import base64
import io
import json
from typing import Protocol

from openai import OpenAI
from PIL import Image

from .config import AppConfig
from .models import ConceptEvaluation


class EvaluationParseError(RuntimeError):
    """Raised when the VLM response does not contain the requested structured result."""


class ImageServices(Protocol):
    def create_initial_prompt(self, concept: str) -> str: ...

    def refine_prompt(
        self,
        concept: str,
        previous_prompt: str,
        evaluation: ConceptEvaluation,
    ) -> str: ...

    def generate_image(self, prompt: str) -> Image.Image: ...

    def evaluate_image(self, concept: str, image: Image.Image) -> ConceptEvaluation: ...


class AIStudioServices:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key.get_secret_value(),
            project=config.folder_id,
        )

    def _text(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.config.text_model,
            input=prompt,
        )
        text = response.output_text.strip()
        if not text:
            raise RuntimeError("The language model returned an empty prompt.")
        return text

    def create_initial_prompt(self, concept: str) -> str:
        return self._text(
            f"""
You write production prompts for YandexART.

Abstract concept: "{concept}"

Create one English image-generation prompt that communicates the concept immediately
through a strong visual metaphor. Specify the subject, environment, composition, palette,
lighting, camera or viewpoint, artistic medium, mood, and meaningful symbolic details.
Prefer concrete visual language over abstract adjectives. Avoid written words, captions,
logos, watermarks, split screens, and collage layouts.

Return only the final YandexART prompt with no title, quotation marks, or explanation.
""".strip()
        )

    def refine_prompt(
        self,
        concept: str,
        previous_prompt: str,
        evaluation: ConceptEvaluation,
    ) -> str:
        feedback = json.dumps(evaluation.model_dump(), ensure_ascii=False, indent=2)
        return self._text(
            f"""
You improve production prompts for YandexART.

Original abstract concept: "{concept}"

Complete previous prompt:
---
{previous_prompt}
---

Vision-model evaluation:
{feedback}

Write a replacement English prompt that directly addresses every recommendation while
preserving the strongest visual decisions. Make the central metaphor more unambiguous,
remove contradictory details, and specify composition, palette, lighting, viewpoint,
medium, and mood. Avoid written words, captions, logos, watermarks, split screens, and
collage layouts.

Return only the complete new YandexART prompt with no commentary.
""".strip()
        )

    def generate_image(self, prompt: str) -> Image.Image:
        response = self.client.images.generate(
            model=self.config.image_model,
            prompt=prompt,
            n=1,
            size=self.config.image_size,
        )
        encoded = response.data[0].b64_json
        if not encoded:
            raise RuntimeError("YandexART returned no image data.")
        image = Image.open(io.BytesIO(base64.b64decode(encoded)))
        image.load()
        return image.convert("RGB")

    @staticmethod
    def _image_data_url(image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=92)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def evaluate_image(self, concept: str, image: Image.Image) -> ConceptEvaluation:
        prompt = f"""
Evaluate how clearly this image communicates the abstract concept "{concept}".

Use a strict 0-100 scale. Reserve 98-100 only for an image whose concept is immediately
unambiguous, whose composition and symbols reinforce it, and which contains no meaningful
contradiction or distracting element. A beautiful image is not automatically a good match.

Return:
- fit_percent: the numeric concept-fit score
- strengths: short concrete observations about what already works
- recommendations: short actionable visual changes needed for the next prompt; return an
  empty list only if the score is at least 98
""".strip()
        response = self.client.responses.parse(
            model=self.config.vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": self._image_data_url(image),
                            "detail": "auto",
                        },
                    ],
                }
            ],
            text_format=ConceptEvaluation,
        )
        if response.output_parsed is None:
            raise EvaluationParseError("The vision model returned no structured evaluation.")
        return response.output_parsed

