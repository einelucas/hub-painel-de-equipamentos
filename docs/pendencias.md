# Pendências de verificação

Este documento registra itens ocultos ou adiados na interface que dependem de decisão e homologação. A existência de uma rota sem entrada de menu é intencional nesses casos e não deve ser tratada como bug.

## Aba Jurídico oculta na navbar

**Data da ocultação:** 2026-11-04.

### O que foi feito

- O item `Jurídico` permanece em `NAV_ITEMS`, em `frontend/utils/navigation.ts`, com `hidden: true`.
- `visibleNavItems` passou a descartar itens com `hidden`, além do filtro por permissão. A navbar (`frontend/components/TabsNav.vue`) não renderiza a aba.
- A rota `/juridico` continua em `NAV_ITEMS`, portanto `activeNavPath` segue mapeando a URL para o item quando recebe a lista completa. Como `TabsNav` calcula o ativo apenas sobre os itens visíveis, abrir `/juridico` direto não destaca nenhuma aba — comportamento esperado.

### O que não foi alterado

- A página `frontend/pages/juridico.vue` e a rota `/juridico` continuam existindo e acessíveis por URL direta.
- Permissões, endpoints de backend e a fila `/queues/legal` continuam ativos. As APIs de processo jurídico não foram removidas nem bloqueadas.
- Nenhum link interno foi reescrito.

A rota `/juridico` existir sem entrada na navbar é **intencional**, não um bug.

### O que verificar depois

- [ ] Validar se o acesso direto a `/juridico` deve continuar liberado para todos os perfis ou ser bloqueado/restrito.
- [ ] Confirmar com a equipe Jurídico se é necessário um ponto de entrada alternativo (atalho, link em tela de processo ou dashboard).
- [ ] Revisar links internos e atalhos que apontem para `/juridico`.
- [ ] Confirmar com o time de negócio a data ou o critério para reexibir a aba.
- [ ] Revisar os testes de backend e a fila `/queues/legal` para garantir que a ocultação visual não afetou os fluxos operacionais.
- [ ] Rodar os testes do frontend: `npm test` ou `npx vitest run tests/navigation.test.ts` em `frontend/`.

### Como reativar

1. Remover `hidden: true` do item `Jurídico` em `frontend/utils/navigation.ts`.
2. Ajustar os testes de `visibleNavItems` em `frontend/tests/navigation.test.ts` (contagens e asserção de que `/juridico` não aparece).
3. Rodar os testes do frontend.
4. Atualizar este documento e [funcionalidades](funcionalidades.md).
