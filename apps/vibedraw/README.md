# VibeDraw

VibeDraw is a local Gradio demo that makes an agentic image-generation loop visible. Enter an abstract concept, then watch an LLM write a YandexART prompt, YandexART produce an image, and a VLM score and critique the result. The prompt is refined until the image reaches 98% or five iterations have run.

## Run locally

The repository root must contain a `.env` file:

```text
folder_id=...
api_key=...
```

From this directory:

```powershell
uv sync
uv run python app.py
```

Open `http://127.0.0.1:7860`. The API key remains in the Python process and is never sent to the browser.

## What to expect

- Every run can make up to five LLM, image-generation, and VLM calls. These are paid Yandex AI Studio requests.
- The Stop button cancels the Gradio generator after the API call currently in progress returns.
- Images and prompts live only for the browser session. Use **Download run** to save a ZIP with all images, the best image, and `manifest.json`.
- The VLM percentage is a model judgment, not an objective artistic measurement. The strict rubric makes the loop useful for demonstration, but scores can still regress between iterations.

## Test without API calls

```powershell
uv run pytest
```

The automated tests use fake services and never call AI Studio.

