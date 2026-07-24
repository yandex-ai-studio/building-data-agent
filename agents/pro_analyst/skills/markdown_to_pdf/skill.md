---
id: markdown_to_pdf
name: Markdown To PDF
description: Convert markdown reports into PDF output.
tags: [markdown, pdf, report]
---

# Markdown To PDF

Use this skill when the user asks for a PDF report from markdown or when a report should be delivered as PDF.

Preferred workflow:

1. Create or read the source markdown.
2. Convert the markdown to PDF inside Code Interpreter.
3. Use Python packages available in the container, such as `reportlab`, `markdown`, or another suitable converter. Install packages inside the container if necessary.
4. Keep PDF layout simple and readable: title, section headings, paragraphs, tables, and embedded charts where useful.
5. Save the PDF file and return it in the final answer.

Fallback workflow:

If the user has a local command-line converter already installed and explicitly wants local conversion, use `execute_command` with an allowed shell entrypoint to call that utility. Do not add PDF conversion dependencies to the local `ma` project unless the user requests a separate local feature.
