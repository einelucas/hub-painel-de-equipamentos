# Design QA — filtros, diálogos e controles Vuetify

Status: **aprovado** em 2026-10-29.

Final result: **passed**.

## Visual truth

- Source: screenshots attached by the user in the request, showing neutral outlined filters/buttons and a primary-blue focused outline with a floating label.
- Earlier filter/dialog references:
  - `/tmp/codex-remote-attachments/01a1110d-df1b-7272-908c-3daec6b7601e/5475ed5f-f3cc-481d-9e86-dad6b475c1bb/1-1000440108.jpg`
  - `/tmp/codex-remote-attachments/01a1110d-df1b-7272-908c-3daec6b7601e/5475ed5f-f3cc-481d-9e86-dad6b475c1bb/2-1000440109.jpg`
- Implementation screenshots:
  - `/tmp/vuetify-outline-desktop.png`
  - `/tmp/vuetify-outline-focus.png`
  - `/tmp/vuetify-outline-mobile.png`

## Viewports and states checked

| Viewport | State | Result |
| --- | --- | --- |
| 1440 × 1000 | Equipment filters and actions, default state | Outlined fields and buttons visible and aligned |
| 1440 × 1000 | Unit selector focused/open | 2 px primary-blue outline and floating label visible |
| 768 × 1000 | Equipment filters and actions | Controls wrap without page-level horizontal overflow |

## Focused comparison

- Normal selectors use the native Vuetify 1 px outlined field treatment.
- Focus changes the selector outline to the Hub primary color (`#304f7e`) and 2 px width.
- Outlined action buttons use the native Vuetify 1 px primary border.
- Tonal actions retain their hierarchy and are not forced into the outlined treatment.
- Labels remain legible and float above selected/focused values, matching the supplied reference behavior.

## Regression checklist retained from the filter/dialog QA

- [x] Unidade, Obra e Equipamento maintain equal fixed widths, with or without a selected value.
- [x] Selectors and action buttons remain vertically aligned.
- [x] Floating labels stay centered over the outline notch.
- [x] Dropdowns are teleported above adjacent cards and are not clipped.
- [x] Equipment search remains absent from Equipamentos, Suprimentos and Jurídico.
- [x] Engineering keeps its intentional search field.
- [x] Narrow layouts wrap controls without page-level horizontal overlap.
- [x] Destructive confirmations remain above their parent dialog.

## Issue history

1. **P1 — Outlined controls rendered without borders**
   - Cause: Tailwind preflight reset applied `border-width: 0` after Vuetify 4's layered component rules.
   - Fix: disabled Tailwind preflight so Vuetify remains the single owner of the application reset and its native component borders.
   - Recheck: computed styles show 1 px outlined button/field borders and 2 px focused field borders.

## Final result

**Passed** — no actionable P0, P1, or P2 visual issues remain in the requested button/filter states.

The QA browser could not download Google Fonts because of the environment network policy; the configured system-font fallback was used without geometry or readability regressions.
