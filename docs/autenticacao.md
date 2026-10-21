# Autenticação, autorização e segurança

O módulo combina autenticação local e integração OIDC/Keycloak. A identificação do usuário e as permissões são verificadas no backend; ocultar uma aba na interface não constitui controle de acesso.

## Fluxos de identidade

**Login local:** `POST /api/v1/auth/login` valida o par e-mail/senha contra credenciais persistidas em `User` e `Account`. O backend armazena **hash de senha**, emite sessão e valida token de acesso. `POST /api/v1/auth/logout` encerra sessão; `GET /api/v1/auth/me` retorna dados mínimos de identidade, papel e permissões.

**Primeiro acesso:** existe no código atual um fluxo de alteração de senha via `POST /api/v1/auth/set-password`. A implementação legada utiliza uma **senha inicial compartilhada embutida no código**, com referências também no frontend e em scripts. Isso é uma **pendência de segurança**, não uma prática a seguir em novas integrações. Não publique o valor da senha, mesmo como exemplo. Sua substituição por convite ou ativação individual, token temporário e invalidável e verificação das contas já provisionadas exige mudança de código separada desta documentação.

**OIDC/Keycloak:** o frontend usa configurações públicas de client/issuer/redirect, enquanto o backend verifica tokens, issuer, audience e chaves públicas da identidade. Valores reais da instalação corporativa não pertencem aos arquivos versionados.

## Papéis e escopo

Papéis presentes: `VIEWER`, `ANALYST` e `ADMIN`. `Role` define **o que** pode executar; atribuições por unidade definem **onde** pode operar. As verificações são centralizadas em:

- `backend/app/core/auth.py` — resolução de identidade e dependências de permissão;
- `backend/app/core/permissions.py` — mapa de permissões por papel;
- `backend/app/core/scope.py` — escopo e recursos por unidade;
- `backend/app/modules/access/` — administração de acessos e responsáveis.

ADMIN possui privilégios globais na implementação atual. A matriz corporativa de aprovações por equipe e as responsabilidades definitivas de reabertura podem exigir ajuste organizacional; não assumir permissões adicionais fora do código.

A API deve rejeitar acesso a dados fora do escopo independentemente de parâmetros da URL e filtros da interface.

## Ambiente de desenvolvimento

Há um mecanismo de autenticação de desenvolvimento com identidades artificiais, condicionado a `DEV_AUTH_ENABLED` e a `APP_ENV` não ser produção. Como os tokens de desenvolvimento são previsíveis, **nunca** utilize essa opção em um backend publicamente acessível, mesmo que o ambiente esteja nomeado como development.

Proteja o deploy com autenticação real, escopo de rede e configuração do ambiente; assegure que a configuração efetiva do Railway seja revisada antes da homologação.

## Segredos e dados pessoais

- `DATABASE_URL` e URLs com senhas: segredo de infraestrutura, não frontend nem repositório.
- `GRAPH_CLIENT_SECRET`, `RESEND_API_KEY` e chaves de storage: gerenciador de segredos ou variáveis protegidas do serviço.
- E-mails corporativos, perfis, responsáveis, destinatários e templates customizados: dados administráveis no banco (respeitando permissões e políticas de retenção).
- Senhas individuais: hash seguro no banco; tokens de acesso não devem ser logados.
- XLSX do Monday, LGE, Árvore corporativa, documentos contratuais, relatórios de migração reais e dumps: armazenamento privado autorizado, não Git público.
- Logs e auditoria devem registrar eventos e atores sem revelar credenciais ou anexos desnecessários.

O `.gitignore` ajuda a prevenir novas inclusões, mas **não remove conteúdo que já esteve no histórico Git**. Se credenciais reais forem identificadas em commits anteriores, invalide-as/rotacione-as e planeje tratamento do histórico com a equipe responsável.

## Administração e auditoria

Gerenciamento de usuários (`/usuarios`), acesso por unidade e relatórios de auditoria exigem permissões de backend. A interface de usuários identificada como temporária deve ser avaliada antes do uso corporativo definitivo.

Para testar segurança, inclua casos de usuário inativo, sessão expirada, permissão insuficiente e recurso de outra unidade. Consulte [testes](testes.md).

## Checklist de homologação

- [ ] Credenciais de primeiro acesso compartilhadas eliminadas/rotacionadas e sessões afetadas revistas.
- [ ] Integração de identidade e permissões revisadas com a organização.
- [ ] Bypass de desenvolvimento desabilitado em qualquer serviço público.
- [ ] Segredos protegidos no Railway/ambiente e ausentes do Git atual e de artefatos públicos.
- [ ] Proteção de escopo, acesso administrativo, uploads e exportações testada.
- [ ] Logs, backup, retenção de arquivos e trilha de auditoria revisados.

**Estado:** checklist de validação; marcar um item como concluído requer verificação operacional, não mera presença do código.
