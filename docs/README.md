# Documentação técnica | Painel de Equipamentos

Esta é a referência de **manutenção e homologação da implementação atual** do módulo. Não é um diário de sprints, nem uma coleção de instruções de prompts. A documentação descreve comportamento presente no código; decisões futuras e limitações são diferenciadas da funcionalidade implementada.

## Índice

| Documento | Conteúdo |
| --- | --- |
| [Arquitetura](arquitetura.md) | Camadas, módulos, fluxo de dados, frontend e backend |
| [Funcionalidades](funcionalidades.md) | Navegação, processos e experiência operacional |
| [Domínio e EAP](dominio-eap.md) | Entidades, cardinalidades, workflow e regras canônicas |
| [API](api.md) | Endpoints, contratos, autorização e erros |
| [Autenticação e segurança](autenticacao.md) | Identidade, papéis, escopo e riscos de configuração |
| [Importação Monday](importacao-monday.md) | Perfis, staging, plan, apply, reconciliação e EAP |
| [Notificações](notificacoes.md) | Regras, templates HTML, provedores e outbox |
| [Ambientes e deploy](ambientes-deploy.md) | Execução local, variáveis, migrations e homologação |
| [Testes](testes.md) | CI, testes, proteção de banco e regressão |

O [README principal](../README.md) apresenta o módulo e oferece um início rápido.

## Fonte de verdade

1. Decisões humanas aprovadas e ainda aplicáveis, especialmente na EAP e importação.
2. Código, SQLAlchemy models, migrations Alembic, schemas, controllers, services e testes atuais para descrever a **implementação**.
3. Documentação do produto para orientar uso e manutenção, sem substituir verificação da implementação.
4. Fontes corporativas autorizadas (Árvore oficial para EAP, Monday para equipamentos reais, LGE como referência complementar), sempre fora do repositório público quando confidenciais.

Não se deve deduzir que uma migration já foi aplicada em DEV/produção apenas por existir no Git. A ordem de aplicação requer autorização e validação do ambiente.

## Convenções editoriais

- **Implementado:** há evidência direta no código atual.
- **Configurável:** existe suporte técnico, mas depende de valores e/ou operação externos.
- **Pendente/validar:** depende de decisão, homologação, implantação ou verificação não realizada.
- Exemplo é **sintético**: não inserir e-mails reais, nomes de colaboradores, senhas padrão, hashes, segredos, documentos ou dados de contratos.
- Arquivos Markdown de escopos antigos não são mantidos aqui como fonte normativa; a história do desenvolvimento permanece no Git.

## Como manter atualizada

Ao alterar um endpoint, modelo ou regra de negócio, revise o documento específico e o índice. Evite criar arquivos chamados `etapa-XX`, `MIG-XX`, `ARCH-XX` ou relatórios transitórios dentro de `docs/`. Para decisões e investigações temporárias, use issues e pull requests; consolide no documento de domínio quando a decisão for aprovada.

Antes de excluir uma decisão de negócio, confirme se ela foi realmente substituída. Preserve no documento definitivo qualquer regra aprovada ainda vigente.
