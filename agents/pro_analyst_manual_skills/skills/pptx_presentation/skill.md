---
id: pptx_presentation
name: PPTX Presentation Builder
description: Create polished PowerPoint presentations from analysis outputs.
tags: [pptx, presentation, reporting]
---

# PPTX Presentation Builder

Use this skill when the user asks for a PowerPoint deck or slide-based executive report.

Workflow:

1. Clarify the audience, target slide count, language, and desired emphasis if they are missing.
2. Build the presentation inside Code Interpreter, not in the local `ma` process.
3. In Code Interpreter, use `python-pptx` or another available package. Install packages inside the container if necessary.
4. Prefer a concise structure:
   - Title and purpose
   - Key findings
   - Supporting charts/tables
   - Risks or limitations
   - Recommendations / next steps
5. Save the deck as `.pptx`.
6. Return the `.pptx` file in the final answer and explicitly list its filename.

Do not ask `ma` to install PowerPoint libraries locally. All PPTX generation should happen in Code Interpreter or through a user-approved external command utility if one is already available.
