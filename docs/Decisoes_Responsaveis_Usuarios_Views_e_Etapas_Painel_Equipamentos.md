# Decisões Funcionais — Responsáveis, Views de Engenharia e Usuários

**Projeto:** Hub de Automação → Planejamento → Painel de Equipamentos  
**Data de registro:** 20/09/2026  
**Status:** decisões funcionais confirmadas nesta conversa

## 1. Objetivo

Registrar as decisões tomadas sobre views de Engenharia, responsáveis, usuários, permissões, filtros, Work Packages, criação de novos equipamentos e futura comunicação por e-mail, indicando em qual etapa cada ponto entra.

## 2. View Engenharia MetalMec

A aba **Engenharia MetalMec** do Monday não representa uma entidade separada nem uma tabela própria. Ela é uma visualização dos mesmos equipamentos do quadro principal.

Lógica confirmada:

```text
Fonte: Equipment
Filtro: Disciplina = Metal Mec.
Agrupamento: Responsável
```

Exemplo:

```text
Engenharia MetalMec

Ana Carolina
├── Equipamento A
├── Equipamento B
└── Equipamento C

Uilson
├── Equipamento D
└── Equipamento E
```

Ana Carolina e Uilson são apenas os responsáveis pelos equipamentos exibidos naquele agrupamento. Eles não representam fase, área, departamento, categoria ou Work Package.

### Consequência técnica

O agrupamento deve ser derivado de:

```text
equipment.responsible_user_id
```

E o filtro da view deve utilizar:

```text
equipment.discipline_id
```

Ao trocar o responsável de um equipamento, ele deve aparecer automaticamente no agrupamento do novo responsável.

### Etapa

**Views Operacionais / Saved Views — P2**

Relacionada a:

```text
BE-006 — Saved Views
FE-005 — Editor de Views
```

A tela de Engenharia pode existir antes como view fixa, desde que seja baseada nos dados reais e não em grupos persistidos artificiais.

## 3. Responsável por equipamento

Cada equipamento possui um responsável associado a um usuário real do Hub:

```text
Equipment
└── responsible_user_id → User.id
```

Responsável significa quem acompanha ou responde operacionalmente pelo equipamento.

### Regra importante

**Responsável não é sinônimo de permissão.**

Exemplo:

```text
Responsável: Ana Carolina

Podem editar:
- Ana Carolina
- Uilson
- Gestores
- Administradores
- outros usuários autorizados
```

Permissão é determinada separadamente por:

```text
Role
+
acesso à unidade
+
permissões do sistema
```

### Etapa

A estrutura básica já existe na **Etapa 4 — Autorização e Administração Operacional**.

O refinamento entra em:

```text
FUN-005 — RACI / matriz de permissões
SEC-001 — Permissões por área/ação
```

Deve estar concluído antes da substituição definitiva do Monday.

## 4. Usuários precisam existir no banco

As pessoas que poderão ser responsáveis por equipamentos devem existir como registros reais em `User`.

Não utilizar somente textos soltos como:

```text
Ana Carolina
Uilson
Ediel
Samuel
```

Modelo esperado:

```text
User
├── id
├── name
├── email
├── active
├── role
└── acessos por unidade
```

E:

```text
Equipment
└── responsible_user_id → User.id
```

Isso permite reutilizar a mesma identidade para:

- responsável do equipamento;
- filtro por responsável;
- agrupamento nas views;
- seleção em formulários;
- permissões;
- auditoria;
- notificações;
- disparos de e-mail;
- futuras filas e alertas.

### Etapa

O modelo `User` já existe.

O cadastro dos usuários reais deve acontecer **antes do primeiro apply definitivo do C2**, pois a migração precisa converter nomes do Monday em IDs reais do Hub.

Relacionado diretamente a:

```text
MIG-001.1 — Apply controlado Monday → Hub
```

## 5. Cadastro de nomes e e-mails reais

Posteriormente será fornecida uma relação com nomes e e-mails reais dos usuários.

Estrutura mínima sugerida:

```text
Nome
E-mail
Perfil
Unidade(s)
Ativo
Pode ser responsável?
```

Não gerar e-mails fictícios como dados definitivos.

### Etapa

Antes do primeiro `apply` real da migração C2.

Relacionado a:

```text
MIG-001.1
FUN-005
SEC-001
```

## 6. Seleção de responsável no Hub

O formulário de equipamento deve permitir selecionar um responsável vindo do banco de dados.

Exemplo:

```text
Responsável
[ Ana Carolina ▼ ]
  Ediel
  Samuel
  Uilson
```

O seletor não deve usar lista hardcoded.

O responsável selecionado deve:

- existir;
- estar ativo;
- ter acesso à unidade do equipamento;
- ser armazenado por `User.id`.

### Etapa

Já implementado parcialmente na **Etapa 4**. Deve ser revisado durante a homologação após o cadastro dos usuários reais.

## 7. Filtro por responsável

As telas operacionais devem permitir filtrar equipamentos por responsável usando `responsible_user_id`, e não comparação textual de nomes.

Isso evita problemas com nomes iguais, acentos, abreviações ou alteração de nome.

### Etapa

A estrutura básica já existe. Deve ser mantida nas views operacionais e no futuro sistema de Saved Views.

## 8. Agrupamento por responsável

As views de Engenharia poderão agrupar equipamentos por responsável.

Esse agrupamento é apenas uma forma de apresentação e não deve virar estrutura persistida no banco.

### Etapa

**Views Operacionais / Saved Views — P2**.

## 9. Futuro sistema de notificações e e-mail

Os usuários precisam possuir e-mail real porque futuramente o Hub terá notificações e disparos por e-mail.

Fluxo conceitual:

```text
Equipment
↓
Responsible User
↓
User.email
↓
Notificação / E-mail
```

Possíveis eventos futuros:

```text
FUP
Kickoff
Prazo próximo
Atraso
Alteração de etapa
Contrato
SC/OCI
OC
Outras pendências
```

Ter o e-mail cadastrado não significa disparar mensagens automaticamente. Ainda precisam ser definidos evento, destinatário, antecedência, frequência, repetição, canal e template.

### Etapa

Relacionada a:

```text
DB-003 — Notification / Outbox
INFRA-002 — Worker / Scheduler
BE-003 — Notifications Service
FUN-007 — Política de notificações
```

Prioridade: **P1**.

## 10. Permissões: visualização e edição

O Hub deve reproduzir a necessidade atual do Monday de existir usuários que só visualizam e usuários que podem editar.

Estrutura atual:

```text
VIEWER
ANALYST
ADMIN
```

- `VIEWER`: somente leitura dentro das unidades permitidas.
- `ANALYST`: leitura e edição operacional.
- `ADMIN`: edição + funções administrativas.

### Evolução prevista

Posteriormente pode existir matriz mais fina, por exemplo:

```text
Engenharia → dados técnicos
Jurídico → chamado/minuta/contrato
Suprimentos → SC/OCI/OC/fornecedor
Gestores → leitura ampla
Admin → administração
```

### Etapa

```text
FUN-005 — Definir RACI
SEC-001 — Permissões por área/ação
```

Antes do corte definitivo do Monday.

## 11. Work Packages

### Decisão confirmada

Um equipamento pode possuir **0..N Work Packages**.

Exemplo:

```text
Equipment
├── CAL012
├── CIV014
├── CIV015
└── CIV012
```

Portanto:

```text
Equipment ↔ WorkPackage
```

deve ser uma relação **N:N**.

### Etapa

Essa correção entra em:

```text
MIG-001.1 — Apply controlado Monday → Hub
```

antes da primeira importação real, porque os XLSX já possuem equipamentos com múltiplos Work Packages.

## 12. Criação de novos equipamentos após a migração

Depois que o Hub substituir o Monday, deve ser possível criar novos equipamentos diretamente no Hub.

Dados primários esperados:

```text
Dados gerais
- Nome
- Origem
- Startup
- Disciplina
- Área
- Responsável
- Criticidade
- Work Package(s)
- CAPEX

Componentes
- Nome
- TAG
- Startup
- Setor
- Lead Time
- Dias antes do Startup
- Frete
- Entrega contratual

Processo
- Equalização
- Negociação
- Jurídico
- Contrato
- SC/OCI
- OC
```

Campos que são fórmulas ou mirrors no Monday não devem virar campos de digitação manual apenas para imitar a interface do Monday. Devem ser calculados pelo Hub quando a regra estiver validada.

### Critério de substituição do Monday

O Monday não deve ser descontinuado enquanto não for possível executar no Hub:

```text
Criar equipamento
↓
Adicionar componentes
↓
Informar dados técnicos
↓
Negociação
↓
Jurídico
↓
Contrato
↓
SC/OCI
↓
OC
↓
Conclusão
```

### Etapa

Essa capacidade será consolidada em:

```text
MIG-001.1 — primeira carga real
FUN-001 — fórmulas
FUN-003 — workflow oficial
FUN-005 / SEC-001 — permissões
P1 — documentos, comentários e notificações
P2 — views avançadas
UAT — homologação final
```

## 13. Resumo das decisões por etapa

| Decisão | Situação | Etapa |
|---|---|---|
| Responsável é um `User` real | Confirmada | Já existente / Etapa 4 |
| Responsável ≠ permissão | Confirmada | Etapa 4 + SEC-001 |
| Engenharia MetalMec é view filtrada | Confirmada | Views Operacionais / FE-005 |
| Ana Carolina/Uilson são agrupamentos por responsável | Confirmada | Views Operacionais |
| Cadastro real de nomes/e-mails | Confirmada | Antes do MIG-001.1 apply |
| Responsáveis aparecem no select a partir do banco | Confirmada | Etapa 4 / homologação |
| Filtro usa `responsible_user_id` | Confirmada | Já existente / Views |
| Notificações usam `User.email` | Direção confirmada | DB-003 / BE-003 / FUN-007 |
| VIEWER só visualiza | Confirmada | Já existente |
| ANALYST edita | Confirmada atualmente | Já existente |
| Permissões finas por departamento | Pendente definição | FUN-005 / SEC-001 |
| Equipamento pode ter vários Work Packages | Confirmada | MIG-001.1 |
| `Equipment ↔ WorkPackage` deve ser N:N | Confirmada | MIG-001.1 |
| Novo equipamento será criado no Hub | Confirmada | Fluxo operacional / UAT |
| Fórmulas não devem ser digitadas manualmente | Confirmada como princípio | FUN-001 |
| Não cortar Monday enquanto faltar função operacional | Confirmada | UAT / Cutover |

## 14. Ordem recomendada

```text
1. Finalizar MIG-001.1
↓
2. Cadastrar usuários reais + e-mails
↓
3. Cadastrar/validar áreas, disciplinas e Work Packages
↓
4. Construir mapping Monday → Hub
↓
5. dry-run
↓
6. stage
↓
7. plan
↓
8. revisão humana
↓
9. apply no banco DEV
↓
10. reconcile
↓
11. validar criação/edição manual de equipamentos
↓
12. completar workflow, fórmulas, permissões e telas
↓
13. implementar notificações/e-mails
↓
14. UAT
↓
15. corte do Monday
```

## 15. Princípio funcional adotado

O Hub não deve reproduzir o Monday apenas visualmente. Deve preservar as necessidades do processo usando modelo próprio e estruturado.

```text
Monday View → filtro/agrupamento no Hub
Pessoa em coluna → User
Responsável → relação Equipment → User
Permissão → Role + Scope + Permission
Mirror → JOIN/agregação
Formula → regra calculada
Grupo visual → estado/filtro/agrupamento
Work Packages múltiplos → relação N:N
```

Esse princípio deve orientar as próximas adequações.
