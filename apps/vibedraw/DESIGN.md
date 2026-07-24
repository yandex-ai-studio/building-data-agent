# VibeDraw Design System

## Intent

A workshop participant sits at a bright desk and watches images converge over several slow inference steps. The interface behaves like a neutral light table: the artwork owns the largest surface, while model traces remain close enough to teach from.

## Color

Use a restrained product palette in OKLCH:

```css
--bg: oklch(1 0 0);
--surface: oklch(0.965 0.006 258);
--ink: oklch(0.19 0.02 258);
--muted: oklch(0.46 0.025 258);
--primary: oklch(0.52 0.17 258);
--accent: oklch(0.70 0.15 70);
```

Stage colors use labeled tinted surfaces: cobalt for the initial prompt, violet for refinements, green for evaluation, amber for recommendations, and red for errors. Color never carries meaning alone.

## Typography

Use the system sans-serif stack throughout. Keep the product scale compact: 14px labels and body text, 16–18px section headings, and a 30px application title. Use monospace only for prompt text and technical model identifiers.

## Layout

- A full-width header and concept composer establish the task.
- The desktop workspace uses a 5/7 split: chronological process trace on the left and the current artwork on the right.
- The iteration gallery spans the full width below the workspace.
- Below 900px, stack the trace, light table, and gallery without changing type scale.

## Components

- Controls use 12px radii; primary panels use at most 16px.
- The Generate button is the only filled primary action.
- The Stop button uses the standard stop affordance and remains visible while work is queued.
- Trace entries use a full tinted background and label badge, never a side stripe.
- Empty states explain the next action and show the fixed 98% / five-iteration contract.

## Motion and states

Transitions are limited to 150–200ms state feedback. No page-load choreography. Loading, success, iteration-limit, stopped, and error states must all be explicit. Reduced-motion users receive instant state changes.

