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

---

# Design QA — inputs do formulário de equipamentos

Status: **aprovado** em 2026-10-30.

Final result: **passed**.

## Visual truth

- Source: screenshots anexados pelo usuário na solicitação, com rótulos flutuantes integrados ao contorno e campo de data arredondado com ícone de calendário.
- Implementation screenshot: `/tmp/equipment-form-vuetify-inputs.png`.
- Browser: Chromium headless, device scale factor 1.

## Viewport and state checked

| Viewport | State | Result |
| --- | --- | --- |
| 1280 × 1000 | Modal “Novo equipamento” aberto, nome e Startup preenchidos | Campos contornados, rótulos flutuantes e calendário visíveis; modal sem overflow horizontal |

## Focused comparison

- Nome, CAPEX e valor total agora usam o mesmo campo Vuetify outlined dos seletores.
- Startup e as duas datas contratuais usam rótulo flutuante, ícone de calendário nativo, 49 px de altura e raio de 16 px.
- O formulário não contém mais inputs nativos diretamente sob `.field`.
- Ações administrativas de EAP e criticidade foram preservadas, assim como validação, máscara monetária e submissão.

## Issue history

1. **P1 — campos misturavam controles nativos e Vuetify**
   - Cause: nome, moedas e datas ainda eram renderizados com `<input>` nativo e títulos externos.
   - Fix: migração para `VTextField`; `CurrencyInput` passou a usar o campo Vuetify sem alterar seu contrato de valor.
   - Recheck: 13 campos Vuetify encontrados, zero inputs nativos diretos e zero overflow horizontal.
2. **P2 — Startup era esticado pela linha da ação de criticidade**
   - Cause: alinhamento stretch do grid fazia o campo ocupar toda a altura da linha vizinha.
   - Fix: alinhamento próprio no início da célula e largura integral.
   - Recheck: Startup e datas contratuais medem 49 px de altura.

## Required surfaces

- Typography: preservada pela configuração do tema Vuetify e CSS corporativo.
- Spacing: grid de duas colunas e gaps originais preservados.
- Colors: contorno neutro e primary do Hub preservados.
- Images/assets: nenhuma imagem nova necessária.
- Copy: rótulos e textos funcionais preservados.

## Final result

**Passed** — nenhuma divergência P0, P1 ou P2 permanece nos campos solicitados.

O único erro de console observado foi o bloqueio de rede ao carregar Google Fonts; o fallback local não alterou a geometria validada.
