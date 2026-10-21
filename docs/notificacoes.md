# Central de notificações e modelos de e-mail

O backend possui um módulo de notificações com **regras editáveis, templates HTML persistidos e outbox auditável**. O envio externo é configurável por ambiente; a existência dos endpoints não comprova que o envio live esteja liberado no Railway.

## Estrutura

| Entidade | Responsabilidade |
| --- | --- |
| `notification_event` | Registro de evento associado a equipamento/transição |
| `notification_rule` | Ativação, antecedência, destinatários, inclusão do responsável e textos de regra |
| `email_template` | Assunto, título, introdução, corpo, botão, rodapé, HTML personalizado e opções visuais |
| `email_delivery` | Outbox: destinatários, provedor, modo, texto/HTML, status, tentativas e resultado |

As migrations `0024_notification_delivery`, `0025_email_delivery_provider` e `0026_email_templates` criam/evoluem essas estruturas. Consulte a versão efetivamente aplicada em cada banco antes de ativar a funcionalidade.

## Painel administrativo

A rota de interface `/administracao/notificacoes` é voltada a perfis autorizados. Inclui regras de disparo, editor de modelos, prévia, variáveis e envio de teste. Arquivos de referência:

- `frontend/components/admin/NotificationCenter.vue`
- `EmailTemplateEditor.vue`, `EmailTemplatePreview.vue`, `EmailTemplateVariables.vue` e `EmailTestPanel.vue`
- `backend/app/modules/notifications/controllers.py`, `mail_service.py`, `template_service.py` e `template_renderer.py`

A API expõe `GET/PUT /notifications/rules/{kind}`, `GET/PUT /notifications/templates/{kind}`, reset, preview, test, consulta de entregas, retry e processamento. Veja [API](api.md).

## Regras, destinatários e disparos

As regras ficam no banco, não em listas fixas de e-mails do frontend. A resolução de destinatários pode somar e-mails configurados e o responsável associado, conforme regra e permissões.

Os tipos implementados abrangem eventos de transição, lembretes de startup e alertas de prazo de negociação/entrega, conforme as constantes e serviços atuais. Não inventar frequência, janela de envio ou time zone; conferir valores configurados da instalação.

`app/modules/notifications/mail_service.py` implementa criação de entregas com chave de deduplicação, processamento pendente, controle de concorrência e retry condicionado ao estado. Resposta aceita por um provedor não é necessariamente comprovação de leitura/entrega ao destinatário.

## Editor de modelos e HTML

- `template_renderer.py` define tipos de notificação, variáveis suportadas, layout padrão, texto alternativo e contexto de prévia.
- `template_service.py` consulta/persiste templates, prepara contexto por equipamento, oferece prévia e envio de teste.
- `html_sanitizer.py` permite um subconjunto seguro de tags/atributos/URLs e sanitiza HTML customizado.
- Conteúdo personalizado fica em `email_template`; alterar marca, estilo ou variáveis na UI não deve exigir um novo commit de template operacional, se o editor suportar a alteração.
- A logo pode ser servida por URL HTTPS configurada via `INPASA_EMAIL_LOGO_URL`. Clientes de e-mail têm limitações próprias; CSS inline e tabelas são preferíveis para compatibilidade.

Ao editar um template, faça preview de casos completos e incompletos, teste sanitização e compare texto e HTML. Evite dados corporativos reais em amostras públicas.

## Provedores e modos

A configuração em `backend/app/core/config.py` inclui:

| Variável | Significado |
| --- | --- |
| `NOTIFICATION_PROVIDER` | `graph` ou `resend` |
| `NOTIFICATION_MODE` | `log`, `sandbox` ou `live` |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER` | Microsoft Graph corporativo |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Serviço Resend |
| `NOTIFICATION_TEST_INBOX` | Destino controlado de testes |
| `NOTIFICATION_TIMEZONE` | Fuso dos alertas |
| `APP_PUBLIC_URL` | Links gerados nos e-mails |
| `INPASA_EMAIL_LOGO_URL` | Logo do template por HTTPS |

Segredos permanecem **somente no backend/infraestrutura protegida**. Não salve client secret ou API key como texto de `notification_rule` ou `email_template`.

- **log:** não envia e-mail real; útil para validação controlada.
- **sandbox:** força um destino de teste autorizado e marca o assunto de teste.
- **live:** permite envio real conforme configuração e regras; ações explícitas de teste continuam sujeitas à caixa de teste.

O adaptador `adapter.py` integra OAuth/client credentials do Microsoft Graph ou a API Resend; permissões de mailbox/remetente devem ser concedidas pela equipe responsável.

## Processamento, auditoria e segurança

O backend tem rotinas de enfileiramento e entrega. O endpoint de processamento não substitui sozinho a definição do worker/scheduler em produção. Verifique agendamento, concorrência, retries, observabilidade e limites antes de habilitar envios reais.

Os registros de entrega retêm informações de destinatários e conteúdo. Restringir leitura por permissão administrativa, definir retenção e evitar logs de tokens ou anexos.

## Homologação

1. Aplicar migrations **somente em TEST autorizado** e conferir rollback.
2. Configurar modo `log`, validar regras, cálculos, template e sanitização.
3. Verificar destino e limites no modo `sandbox` com dados sintéticos.
4. Confirmar política de envio com Microsoft 365/Resend e configuração do worker.
5. Testar retry, deduplicação e concorrência, além dos casos sem destinatário.
6. Habilitar `live` apenas após homologação, revisão de permissões e autorização explícita.

Consulte [ambientes](ambientes-deploy.md), [testes](testes.md) e [autenticação](autenticacao.md).
