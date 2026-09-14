---
id: data_exploration
name: Guided Data Exploration
description: Explore a table, summarize structure and quality, then ask what reports to build.
tags: [data, exploration, clarification]
---

# Guided Data Exploration

Use this skill when the user gives a dataset and wants analysis, discovery, or report ideas.

Workflow:

1. Use `ls` to find candidate files.
2. Use `inspect` on the relevant CSV/XLS/XLSX file.
3. Summarize:
   - File and sheet names
   - Row/column counts
   - Column meanings inferred from names and samples
   - Data types
   - Missing values, suspicious values, duplicates, and obvious quality issues
4. Ask the user a clarification question using the clarification tool before building final reports. Offer options such as:
   - Executive overview
   - Trend and segmentation analysis
   - Data quality report
   - Predictive or forecasting analysis
   - Custom answer
5. After the user chooses, use Code Interpreter for deeper analysis and generated outputs.
6. Return all produced files in the final answer.
