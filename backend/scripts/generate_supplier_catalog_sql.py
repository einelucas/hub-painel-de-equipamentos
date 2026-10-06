"""Gera o SQL transacional do catálogo de fornecedores para o editor do Neon.

O arquivo gerado continua seguro por padrão: o operador precisa substituir o
placeholder do banco esperado. A carga valida catálogo/revisão, bloqueia
conflitos, faz upsert somente dos campos oficiais e registra AuditLog.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.modules.supplier_catalog.catalog import CATALOG_PATH, load_catalog, validate_catalog

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "supplier_catalog_neon.sql"
EXPECTED_REVISION = "0014_supplier_history"


def _literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def build_sql(catalog_path: Path = CATALOG_PATH) -> str:
    catalog = load_catalog(catalog_path)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catálogo inválido: " + "; ".join(errors))

    supplier_values = ",\n".join(
        "    ("
        + ", ".join(
            (
                _literal(item.corporate_code),
                _literal(item.legal_name),
                _literal(item.trade_name),
                _literal(item.tax_id),
                "TRUE" if item.active else "FALSE",
                str(item.source_row),
            )
        )
        + ")"
        for item in catalog.ordered_suppliers()
    )
    alias_values = ",\n".join(
        f"    ({_literal(item.corporate_code)}, {_literal(alias)}, {item.source_row})"
        for item in catalog.ordered_suppliers()
        for alias in item.aliases
    )
    catalog_sha = _literal(catalog.sha256)
    source_file = _literal(str(catalog.source.get("file") or "supplier_catalog.json"))

    return f"""-- Catálogo global de fornecedores do Hub
-- Gerado de {catalog.source.get("file")} (SHA-256 da planilha: {catalog.source.get("sha256")})
-- Catálogo JSON SHA-256: {catalog.sha256}
-- Conteúdo: {len(catalog.suppliers)} fornecedores e {sum(len(i.aliases) for i in catalog.suppliers)} aliases.
--
-- INSTRUÇÕES:
-- 1. Substitua SUBSTITUA_PELO_NOME_EXATO_DO_BANCO pelo resultado de SELECT current_database().
-- 2. Execute o arquivo INTEIRO no SQL Editor do Neon.
-- 3. Qualquer conflito gera EXCEPTION e impede o COMMIT de toda a carga.
-- 4. O script não exclui fornecedores e não toca em Equipment/EquipmentSupplier/workflow.

BEGIN;

-- Uma carga administrativa por vez neste banco.
SELECT pg_advisory_xact_lock(hashtext('supplier_catalog:{catalog.sha256}'));

CREATE TEMP TABLE _supplier_catalog_config (
    expected_database text NOT NULL,
    expected_revision text NOT NULL,
    catalog_sha256 text NOT NULL,
    source_file text NOT NULL
) ON COMMIT DROP;

INSERT INTO _supplier_catalog_config VALUES (
    'SUBSTITUA_PELO_NOME_EXATO_DO_BANCO',
    '{EXPECTED_REVISION}',
    {catalog_sha},
    {source_file}
);

DO $$
DECLARE
    cfg _supplier_catalog_config%ROWTYPE;
    actual_revision text;
BEGIN
    SELECT * INTO STRICT cfg FROM _supplier_catalog_config;
    IF cfg.expected_database LIKE 'SUBSTITUA\\_%' ESCAPE '\\' THEN
        RAISE EXCEPTION 'Edite expected_database antes de executar. Banco atual: %', current_database();
    END IF;
    IF current_database() <> cfg.expected_database THEN
        RAISE EXCEPTION 'Banco atual % difere do banco confirmado %',
            current_database(), cfg.expected_database;
    END IF;
    SELECT version_num INTO STRICT actual_revision FROM alembic_version;
    IF actual_revision <> cfg.expected_revision THEN
        RAISE EXCEPTION 'Alembic atual % difere da revisão esperada %',
            actual_revision, cfg.expected_revision;
    END IF;
END $$;

CREATE TEMP TABLE _supplier_catalog_stage (
    corporate_code varchar(20) PRIMARY KEY,
    legal_name varchar(200) NOT NULL,
    trade_name varchar(200),
    tax_id varchar(32) UNIQUE,
    active boolean NOT NULL,
    source_row integer NOT NULL
) ON COMMIT DROP;

INSERT INTO _supplier_catalog_stage
    (corporate_code, legal_name, trade_name, tax_id, active, source_row)
VALUES
{supplier_values};

CREATE TEMP TABLE _supplier_alias_stage (
    corporate_code varchar(20) NOT NULL,
    alias varchar(200) NOT NULL,
    source_row integer NOT NULL,
    PRIMARY KEY (corporate_code, alias),
    UNIQUE (alias)
) ON COMMIT DROP;

INSERT INTO _supplier_alias_stage (corporate_code, alias, source_row)
VALUES
{alias_values};

DO $$
DECLARE
    supplier_count integer;
    active_count integer;
    inactive_count integer;
    alias_count integer;
    conflict record;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE active), count(*) FILTER (WHERE NOT active)
      INTO supplier_count, active_count, inactive_count
      FROM _supplier_catalog_stage;
    SELECT count(*) INTO alias_count FROM _supplier_alias_stage;
    IF (supplier_count, active_count, inactive_count, alias_count) <> (122, 120, 2, 56) THEN
        RAISE EXCEPTION 'Contagens inesperadas: suppliers=%, active=%, inactive=%, aliases=%',
            supplier_count, active_count, inactive_count, alias_count;
    END IF;

    SELECT c.corporate_code AS catalog_code, c.tax_id, s.id, s.corporate_code AS database_code
      INTO conflict
      FROM _supplier_catalog_stage c
      JOIN supplier s ON s.tax_id = c.tax_id
     WHERE s.corporate_code IS DISTINCT FROM c.corporate_code
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Conflito de tax_id %: catálogo %, banco % (Supplier %)',
            conflict.tax_id, conflict.catalog_code, conflict.database_code, conflict.id;
    END IF;

    SELECT a.alias, a.corporate_code AS catalog_code, s.corporate_code AS database_code
      INTO conflict
      FROM _supplier_alias_stage a
      JOIN supplier_alias sa
        ON sa.source = 'SUPPLIER_CATALOG'
       AND sa.context = 'GLOBAL'
       AND sa.alias = a.alias
      JOIN supplier s ON s.id = sa.supplier_id
     WHERE s.corporate_code IS DISTINCT FROM a.corporate_code
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Conflito de alias %: catálogo %, banco %',
            conflict.alias, conflict.catalog_code, conflict.database_code;
    END IF;
END $$;

CREATE TEMP TABLE _supplier_catalog_actions ON COMMIT DROP AS
SELECT
    c.*,
    s.id AS supplier_id,
    CASE
        WHEN s.id IS NULL THEN 'CREATE'
        WHEN s.legal_name IS NOT DISTINCT FROM c.legal_name
         AND s.trade_name IS NOT DISTINCT FROM c.trade_name
         AND s.tax_id IS NOT DISTINCT FROM c.tax_id
         AND s.active IS NOT DISTINCT FROM c.active THEN 'UNCHANGED'
        ELSE 'UPDATE'
    END AS action,
    CASE WHEN s.id IS NULL THEN NULL ELSE jsonb_build_object(
        'legal_name', s.legal_name,
        'trade_name', s.trade_name,
        'tax_id', s.tax_id,
        'active', s.active
    ) END AS previous_data,
    jsonb_build_object(
        'corporate_code', c.corporate_code,
        'legal_name', c.legal_name,
        'trade_name', c.trade_name,
        'tax_id', c.tax_id,
        'active', c.active
    ) AS new_data
FROM _supplier_catalog_stage c
LEFT JOIN supplier s ON s.corporate_code = c.corporate_code;

INSERT INTO supplier
    (id, corporate_code, legal_name, trade_name, tax_id, active, created_at, updated_at)
SELECT
    gen_random_uuid()::text,
    corporate_code,
    legal_name,
    trade_name,
    tax_id,
    active,
    CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
    CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
FROM _supplier_catalog_actions
WHERE action = 'CREATE';

UPDATE _supplier_catalog_actions a
SET supplier_id = s.id
FROM supplier s
WHERE s.corporate_code = a.corporate_code
  AND a.supplier_id IS NULL;

UPDATE supplier s
SET legal_name = a.legal_name,
    trade_name = a.trade_name,
    tax_id = a.tax_id,
    active = a.active,
    updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
FROM _supplier_catalog_actions a
WHERE a.action = 'UPDATE'
  AND s.id = a.supplier_id;

INSERT INTO "AuditLog"
    (id, "userId", action, entity, "entityId", "previousData", "newData", metadata, "createdAt")
SELECT
    gen_random_uuid()::text,
    NULL,
    CASE a.action
        WHEN 'CREATE' THEN 'supplier_catalog.create'
        ELSE 'supplier_catalog.update'
    END,
    'Supplier',
    a.supplier_id,
    a.previous_data,
    a.new_data,
    jsonb_build_object(
        'catalogSha256', cfg.catalog_sha256,
        'corporateCode', a.corporate_code,
        'sourceFile', cfg.source_file,
        'sourceRow', a.source_row
    ),
    CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
FROM _supplier_catalog_actions a
CROSS JOIN _supplier_catalog_config cfg
WHERE a.action IN ('CREATE', 'UPDATE');

CREATE TEMP TABLE _supplier_alias_to_create ON COMMIT DROP AS
SELECT a.*, s.id AS supplier_id
FROM _supplier_alias_stage a
JOIN supplier s ON s.corporate_code = a.corporate_code
LEFT JOIN supplier_alias existing
  ON existing.source = 'SUPPLIER_CATALOG'
 AND existing.context = 'GLOBAL'
 AND existing.alias = a.alias
WHERE existing.id IS NULL;

INSERT INTO supplier_alias (id, supplier_id, alias, source, context, created_at)
SELECT
    gen_random_uuid()::text,
    supplier_id,
    alias,
    'SUPPLIER_CATALOG',
    'GLOBAL',
    CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
FROM _supplier_alias_to_create;

INSERT INTO "AuditLog"
    (id, "userId", action, entity, "entityId", "previousData", "newData", metadata, "createdAt")
SELECT
    gen_random_uuid()::text,
    NULL,
    'supplier_catalog.alias_create',
    'SupplierAlias',
    sa.id,
    NULL,
    jsonb_build_object(
        'supplierId', sa.supplier_id,
        'alias', sa.alias,
        'source', sa.source,
        'context', sa.context
    ),
    jsonb_build_object(
        'catalogSha256', cfg.catalog_sha256,
        'corporateCode', pending.corporate_code,
        'sourceFile', cfg.source_file,
        'sourceRow', pending.source_row
    ),
    CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
FROM _supplier_alias_to_create pending
JOIN supplier_alias sa
  ON sa.supplier_id = pending.supplier_id
 AND sa.source = 'SUPPLIER_CATALOG'
 AND sa.context = 'GLOBAL'
 AND sa.alias = pending.alias
CROSS JOIN _supplier_catalog_config cfg;

DO $$
DECLARE
    mismatched integer;
    linked_aliases integer;
BEGIN
    SELECT count(*) INTO mismatched
    FROM _supplier_catalog_stage c
    LEFT JOIN supplier s ON s.corporate_code = c.corporate_code
    WHERE s.id IS NULL
       OR s.legal_name IS DISTINCT FROM c.legal_name
       OR s.trade_name IS DISTINCT FROM c.trade_name
       OR s.tax_id IS DISTINCT FROM c.tax_id
       OR s.active IS DISTINCT FROM c.active;
    IF mismatched <> 0 THEN
        RAISE EXCEPTION 'Verificação final encontrou % fornecedor(es) divergente(s)', mismatched;
    END IF;

    SELECT count(*) INTO linked_aliases
    FROM _supplier_alias_stage a
    JOIN supplier s ON s.corporate_code = a.corporate_code
    JOIN supplier_alias sa
      ON sa.supplier_id = s.id
     AND sa.source = 'SUPPLIER_CATALOG'
     AND sa.context = 'GLOBAL'
     AND sa.alias = a.alias;
    IF linked_aliases <> 56 THEN
        RAISE EXCEPTION 'Verificação final encontrou % aliases; esperado 56', linked_aliases;
    END IF;
END $$;

-- Resultado desta execução antes do COMMIT.
SELECT action, count(*) AS suppliers
FROM _supplier_catalog_actions
GROUP BY action
ORDER BY action;

SELECT count(*) AS aliases_created
FROM _supplier_alias_to_create;

SELECT count(*) AS extra_in_database
FROM supplier s
WHERE NOT EXISTS (
    SELECT 1 FROM _supplier_catalog_stage c WHERE c.corporate_code = s.corporate_code
);

-- Verificação final dentro da mesma transação: deve retornar 122, 120, 2 e 56.
SELECT
    count(*) AS catalog_suppliers,
    count(*) FILTER (WHERE s.active) AS active,
    count(*) FILTER (WHERE NOT s.active) AS inactive,
    (
        SELECT count(*)
        FROM _supplier_alias_stage a
        JOIN supplier alias_supplier ON alias_supplier.corporate_code = a.corporate_code
        JOIN supplier_alias sa
          ON sa.supplier_id = alias_supplier.id
         AND sa.alias = a.alias
         AND sa.source = 'SUPPLIER_CATALOG'
         AND sa.context = 'GLOBAL'
    ) AS catalog_aliases
FROM supplier s
WHERE s.corporate_code IN (SELECT corporate_code FROM _supplier_catalog_stage);

COMMIT;
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    sql = build_sql(args.catalog)
    args.out.write_text(sql, encoding="utf-8")
    print(f"SQL gerado em {args.out} ({len(sql.splitlines())} linhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
