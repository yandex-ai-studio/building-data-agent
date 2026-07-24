---
id: docx_document
name: DOCX Document Builder
description: Create Word-compatible analytical documents and reports.
tags: [docx, document, report]
---

# DOCX Document Builder

Use this skill when the user asks for a Word document, memo, brief, or formatted analytical report.

Workflow:

1. Clarify audience, length, language, and required sections if needed.
2. Draft a clear outline before generating the final file.
3. Build the document inside Code Interpreter, not in the local `ma` process.
4. In Code Interpreter, use `python-docx` or another available package. Install packages inside the container if necessary.
5. Include headings, concise paragraphs, tables, and referenced figures where useful.
6. Save the document as `.docx`.
7. Return the `.docx` file in the final answer and explicitly list its filename.

Do not add DOCX-generation libraries to the local project dependencies.
