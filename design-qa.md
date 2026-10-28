# Design QA — filtros e camadas de diálogo

Status: **aprovado** em 2026-10-28.

Final result: **passed**.

## Referências

- `/tmp/codex-remote-attachments/01a1110d-df1b-7272-908c-3daec6b7601e/5475ed5f-f3cc-481d-9e86-dad6b475c1bb/1-1000440108.jpg`
- `/tmp/codex-remote-attachments/01a1110d-df1b-7272-908c-3daec6b7601e/5475ed5f-f3cc-481d-9e86-dad6b475c1bb/2-1000440109.jpg`

## Evidências locais

- Desktop: `/tmp/equipamentos-filtros-desktop.png`
- Dropdown aberto: `/tmp/equipamentos-filtros-dropdown.png`
- Tablet: `/tmp/equipamentos-filtros-tablet.png`

## Checklist

- [x] Unidade, Obra e Equipamento mantêm a mesma largura (248 px no viewport de 1440 px), com ou sem valor.
- [x] Seletores têm wrapper de 46 px e contorno visível de 41 px; botões de ação seguem os 41 px visuais e ficam alinhados pela base.
- [x] Rótulos flutuantes ficam centralizados sobre o recorte da borda, sem deslocamento causado pelo ícone.
- [x] O dropdown é teleportado para o `body` com `z-index: 2001` e não é cortado pelos cards seguintes.
- [x] O campo e o botão de busca não aparecem em Equipamentos, Suprimentos ou Jurídico.
- [x] A busca continua disponível na fila de Engenharia, que não fazia parte da remoção solicitada.
- [x] Em largura reduzida, seletores e ações quebram em linhas completas sem sobreposição horizontal.
- [x] A confirmação destrutiva usa `z-index: 10000`, acima dos diálogos do Element Plus.

Observação: no navegador de QA, o carregamento da fonte Google foi bloqueado pela política de rede do ambiente; a pilha de fontes do sistema foi usada como fallback sem alterar geometria ou legibilidade.
