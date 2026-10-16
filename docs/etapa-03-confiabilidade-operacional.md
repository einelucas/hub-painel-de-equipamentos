# Etapa 3 — Confiabilidade operacional

## Limites de registros

As listas visíveis continuam paginadas no servidor. Operações que precisam do conjunto completo
(seletor global, filtro da auditoria, Kanban e exportação) percorrem todas as páginas anunciadas
pela API. O antigo corte silencioso de 20 páginas/2.000 equipamentos foi removido.

O carregador compartilhado recusa paginação inválida, mais de 10.000 páginas ou mudança do total
durante a leitura. Nesses casos nenhum conjunto parcial é apresentado como completo.

## Importação Monday retomável

O job agora persiste o mapping usado para gerar o plano, contador de tentativas, lease e heartbeat.
O worker atualiza o heartbeat a cada 15 segundos. Na inicialização da API e durante o polling, um
job `RUNNING` sem heartbeat por dois minutos pode ser assumido atomicamente por uma nova instância.

O apply continua usando uma transação única: uma interrupção reverte os dados de domínio; a nova
tentativa reconstrói e valida o plano pelo mesmo hash. O lease impede que um worker antigo finalize
o estado de um job que já foi assumido por outro processo.

A migration necessária é `0022_resilient_apply_jobs`:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

## Arquivos de contratos

Em desenvolvimento, `STORAGE_PROVIDER=local` grava em `STORAGE_LOCAL_DIR`. Produção exige
`STORAGE_PROVIDER=s3`, que funciona com AWS S3 e serviços compatíveis, incluindo Railway Bucket.

Variáveis de produção:

```dotenv
STORAGE_PROVIDER=s3
STORAGE_S3_BUCKET=nome-do-bucket
STORAGE_S3_ENDPOINT_URL=https://endpoint-do-provedor
STORAGE_S3_REGION=regiao
STORAGE_S3_ACCESS_KEY_ID=...
STORAGE_S3_SECRET_ACCESS_KEY=...
STORAGE_S3_PREFIX=production
```

Na AWS, endpoint e credenciais explícitas podem ficar vazios quando a cadeia padrão de credenciais
estiver disponível. O upload aceita no máximo 20 MB e lê somente 20 MB + 1 byte da requisição.

A troca de arquivo é compensável: o novo objeto é salvo, o banco é confirmado e só então o objeto
anterior é removido. Se o commit falhar, o novo objeto é apagado. Ao excluir um contrato, o banco é
confirmado antes da limpeza do objeto, evitando perder um arquivo ainda referenciado após rollback.
