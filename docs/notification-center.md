# Central de notificações — Microsoft Graph + Resend

**Implementação:** módulo administrativo em Equipamentos → Administração → Notificações,
ou rota direta de ADMIN: \`/administracao/notificacoes\`. A API está sob \`/api/v1/notifications\`.

## 1. Preparação do banco e ambientes

Migration: \`0024_notification_delivery\`. **Nunca aplique em DEV/produção sem autorização.**
Aplicar somente em banco TEST dedicado e homologar antes de promover.

Novas tabelas: \`notification_rule\` (um conjunto corporativo de regras) e
\`email_delivery\` (outbox idempotente, status, tentativas, auditoria).
\`notification_event\` legado continua preservado para histórico do fluxo.

## 2. Provedores de e-mail (somente backend)

\`\`\`dotenv
NOTIFICATION_MODE=log
NOTIFICATION_PROVIDER=graph
RESEND_API_KEY=
RESEND_FROM_EMAIL=
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
GRAPH_SENDER=
NOTIFICATION_TEST_INBOX=
NOTIFICATION_TIMEZONE=America/Sao_Paulo
\`\`\`

**Resend para testes (inclusive Gmail pessoal)**: crie uma API key em
<https://resend.com/api-keys>, configure `RESEND_API_KEY` e `RESEND_FROM_EMAIL`
(o remetente fornecido pelo Resend, como `onboarding@resend.dev`, está sujeito
a restrições de teste; para outros destinatários, verifique um domínio).
Use `NOTIFICATION_MODE=sandbox`, `NOTIFICATION_PROVIDER=resend` e
`NOTIFICATION_TEST_INBOX=seu@gmail.com`. A caixa pessoal deve pertencer à
mesma conta autorizada para testes e receber **somente dados sintéticos**.
Não compartilhe informações empresariais com serviços externos sem aprovação.

**Microsoft Graph corporativo**: o administrador do Microsoft Entra ID precisa criar um aplicativo com credenciais
de aplicação, conceder **Microsoft Graph Mail.Send (Application)** mediante consentimento
administrativo e limitar o acesso do app às caixas autorizadas no Exchange Online
(por exemplo, RBAC for Applications). A conta \`GRAPH_SENDER\` deve existir e ter licença
e permissões adequadas. Nunca coloque segredos no Git, browser, logs ou no banco.

O serviço usa OAuth 2.0 client credentials e \`POST /v1.0/users/{sender}/sendMail\`,
com \`saveToSentItems=true\`. HTTP 202 significa **aceite para processamento**, NÃO
garantia de entrega.

## 3. Modos seguros

- \`log\` (padrão): nenhuma rede, status \`SIMULATED\`. Pode-se desenvolver e validar
  templates sem Microsoft 365.
- \`sandbox\`: Graph envia todas as mensagens **somente** à caixa fixa
  \`NOTIFICATION_TEST_INBOX\`; o assunto recebe \`[TESTE HUB]\`. Destinatários originais
  ficam no histórico para inspeção e nunca recebem mensagens.
- \`live\`: Graph envia aos destinatários da regra; no botão **Enviar teste**, o destino
  ainda é exclusivamente \`NOTIFICATION_TEST_INBOX\`.

**Fluxo recomendado**: configure \`sandbox\` e um e-mail interno autorizado,
homologue o envio à caixa (inclusive o Spam) e os registros, depois autorize a
mudança de ambiente para \`live\` com restrições de acesso. Não ativar regras sem
homologação.

## 4. Regras operacionais

Todas começam **desativadas**. Podem ser configuradas na UI:

- \`KICKOFF\`: após a transição 5→6 do equipamento;
- \`FUP\`: após a transição 7→8;
- \`STARTUP_REMINDER\`: aviso na data do startup menos \`daysBefore\` dias,
  para equipamentos com status \`ACTIVE\`, executado pelo worker.
- \`NEGOTIATION_OVERDUE\`: negociação ainda pendente e prazo calculado vencido, uma vez por prazo.
- \`DELIVERY_REMINDER\`: data-limite de entrega em obra calculada, menos \`daysBefore\` dias.
- \`COMPLETED\`: avanço 7→8, com regra separada do FUP.

Cada regra permite destinatários fixos, incluir responsável do equipamento,
assunto e corpo em texto simples. Variáveis permitidas: \`{equipamento}\`,
\`{obra}\`, \`{responsavel}\`, \`{fase}\`, \`{evento}\`, \`{data}\`.
A UI não permite configurar credenciais Graph/Resend. Para novas regras de prazo
de negociação e entrega, confirmar fórmulas/gatilhos com o Planejamento antes
de codificar ou ativar notificações automáticas.

## 5. Worker e entrega

O backend **não** envia mensagens dentro da transação do workflow. Ele grava
a outbox, que exige execução periódica do worker:

\`\`\`bash
cd backend
python -m app.modules.notifications.cli
\`\`\`

Exemplo: Railway Cron Job usando o mesmo código/backend e o mesmo banco,
a cada hora, com credenciais próprias. A deduplicação do evento de transição
e da data de startup evita reenvio a cada execução. Claims SQL \`FOR UPDATE
SKIP LOCKED\` impedem processamento paralelo do mesmo item.

Em falha/timeout o registro é \`FAILED\`. Não existe retry automático,
porque um timeout após o Graph aceitar a mensagem pode resultar em
duplicação. O administrador deve conferir no Microsoft 365 antes de
solicitar reenvio, até três tentativas. Um worker interrompido marca o
envio \`PROCESSING\` antigo como indeterminado, para revisão.

## 6. Critérios de aceite

1. \`NOTIFICATION_MODE=log\` nunca produz tráfego de e-mail e grava \`SIMULATED\`.
2. \`sandbox\` envia *exclusivamente* à caixa autorizada mesmo que a regra tenha
   destinatários reais.
3. Sem credenciais do provedor, a interface indica configuração incompleta,
   sem expor client secret, Resend API key ou bearer token.
4. Permissão administrativa é validada no backend.
5. Regra desativada não enfileira novo e-mail; transição continua funcionando.
6. Mesma transição/data nunca gera duplicação na outbox.
7. O banco, o histórico e a UI distinguem \`ACCEPTED\` de entrega confirmada.
8. Crash/timeout não causa reenvio automático do mesmo evento.
9. Uma execução do cron gera lembretes de startup apenas na data configurada.
10. Homologação final em TEST antes de configurar o modo live em produção.

## Limitações deliberadas

- As regras são globais/corporativas. Grupos Microsoft 365, hierarquia de chefias
  e destinatários diferentes por obra ainda dependem de decisão organizacional.
- Não inclui assinatura DKIM/SPF (administração do domínio Microsoft 365).
- Não inclui webhooks de confirmação de entrega; Graph sendMail não os fornece
  no retorno HTTP 202.
- O histórico legacy \`notification_event\` conserva os status antigos, enquanto
  \`email_delivery\` é a fonte de verdade para os novos envios.

## Configuração de teste Resend + Gmail

```dotenv
NOTIFICATION_PROVIDER=resend
NOTIFICATION_MODE=sandbox
NOTIFICATION_TEST_INBOX=seuemail@gmail.com
RESEND_API_KEY=
RESEND_FROM_EMAIL=onboarding@resend.dev
```

Utilize o mesmo e-mail com que a conta Resend foi criada para os primeiros
ensaios com `onboarding@resend.dev`, conforme regras de sandbox do provedor.
Configure o endereço e a chave apenas nas variáveis de ambiente do Railway.
Os campos Graph podem permanecer vazios até a autorização da TI.

Após liberar Graph, configure suas variáveis sem remover o Resend e altere
`NOTIFICATION_PROVIDER=graph` e `NOTIFICATION_MODE=live` para o serviço
operacional. A central permite escolher Resend ou Graph **para o botão de
 teste**, mesmo com o Graph como provedor operacional; a caixa de testes nunca
é substituída pelos destinatários reais.
