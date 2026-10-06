-- Catálogo global de fornecedores do Hub
-- Gerado de fornecedores_hub_oficiais.xlsx (SHA-256 da planilha: e241e39f97295e7e436143353f70031865154e84dea21d0ff61dbb51427b07ad)
-- Catálogo JSON SHA-256: e41eed9c1e53a64dc459647117fe04abe1481d747686acf8a0a7945364a3e337
-- Conteúdo: 122 fornecedores e 56 aliases.
--
-- INSTRUÇÕES:
-- 1. Substitua SUBSTITUA_PELO_NOME_EXATO_DO_BANCO pelo resultado de SELECT current_database().
-- 2. Execute o arquivo INTEIRO no SQL Editor do Neon.
-- 3. Qualquer conflito gera EXCEPTION e impede o COMMIT de toda a carga.
-- 4. O script não exclui fornecedores e não toca em Equipment/EquipmentSupplier/workflow.

BEGIN;

-- Uma carga administrativa por vez neste banco.
SELECT pg_advisory_xact_lock(hashtext('supplier_catalog:e41eed9c1e53a64dc459647117fe04abe1481d747686acf8a0a7945364a3e337'));

CREATE TEMP TABLE _supplier_catalog_config (
    expected_database text NOT NULL,
    expected_revision text NOT NULL,
    catalog_sha256 text NOT NULL,
    source_file text NOT NULL
) ON COMMIT DROP;

INSERT INTO _supplier_catalog_config VALUES (
    'SUBSTITUA_PELO_NOME_EXATO_DO_BANCO',
    '0014_supplier_history',
    'e41eed9c1e53a64dc459647117fe04abe1481d747686acf8a0a7945364a3e337',
    'fornecedores_hub_oficiais.xlsx'
);

DO $$
DECLARE
    cfg _supplier_catalog_config%ROWTYPE;
    actual_revision text;
BEGIN
    SELECT * INTO STRICT cfg FROM _supplier_catalog_config;
    IF cfg.expected_database LIKE 'SUBSTITUA\_%' ESCAPE '\' THEN
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
    ('10304', 'NOVATEC COMERCIO E SERVICOS DE COMUNICACOES LTDA EPP', NULL, '18403195000186', TRUE, 84),
    ('1044', 'WAYNE INDUSTRIA E COMERCIO LTDA', NULL, '42120394000676', TRUE, 118),
    ('1061', 'TECNAL IND. COM. IMP. E ESP. DE EQUIP. LABORATORIO LTDA', NULL, '47010566000168', TRUE, 104),
    ('1065', 'SARTORIUS DO BRASIL LTDA', NULL, '03437141000164', TRUE, 93),
    ('10729', 'PETRO TANQUE METALURGICA LTDA.', NULL, '02324640000182', TRUE, 86),
    ('10794', 'TRANE EXPORT LLC', NULL, NULL, TRUE, 109),
    ('10987', 'DRYERATION INDUSTRIA COMERCIO E PROJETOS LTDA', NULL, '87744546000135', TRUE, 34),
    ('1133', 'SMART HEAT DO BRASIL LTDA', NULL, '12915384000151', TRUE, 100),
    ('11444', 'COONTROL TECNOLOGIA EM COMBUSTÃO LTDA', NULL, '17286644000190', TRUE, 28),
    ('11843', 'NOVA ERA EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '04308662000184', TRUE, 83),
    ('12250', 'CUMMINS VENDAS E SERVICOS DE MOTORES E GERADORES LTDA', NULL, '61838884000304', TRUE, 30),
    ('12903', 'MERC - COMERCIO DE MATERIAIS PARA CONSTRUCAO LTDA', NULL, '08760239000171', TRUE, 76),
    ('1303', 'ENDRESS+HAUSER CONTROLE E AUTOMAÇÃO LTDA.', NULL, '49423619000106', TRUE, 38),
    ('1304', 'METALMAG PRODUTOS MAGNÉTICOS LTDA', NULL, '43369974000150', TRUE, 78),
    ('135', 'WEG EQUIPAMENTOS ELETRICOS S/A', NULL, '07175725001050', TRUE, 120),
    ('136', 'TIBRE INDUSTRIA METALURGICA LTDA', NULL, '88209176000280', TRUE, 107),
    ('13974', 'AGI BRASIL INDUSTRIA E COMERCIO S.A.', NULL, '58764309000138', TRUE, 7),
    ('13978', 'IMTAB EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '14164437000175', TRUE, 60),
    ('1402', 'BERMO VALVULAS E EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '82662263000120', TRUE, 20),
    ('14250', 'WEG EQUIPAMENTOS E LOGISTICA LTDDA', NULL, '10953379000108', TRUE, 119),
    ('14318', 'ABERKO VASOS DE PRESSAO LTDA', NULL, '57571697000178', TRUE, 3),
    ('14476', 'CSB ARMAZENS E SERVICOS LTDA', NULL, '45992456000113', TRUE, 29),
    ('1469', 'SCANJET MARINE AND SYSTEMS AB', NULL, NULL, TRUE, 95),
    ('15723', 'WEG TURBINAS E SOLAR LTDA', NULL, '84584994000716', TRUE, 121),
    ('161', 'APLUS ENGENHARIA LTDA.', NULL, '21558706000143', TRUE, 14),
    ('16905', 'APS COMPONENTES ELETRICOS SA', NULL, '04031962000169', TRUE, 15),
    ('17295', 'PAQUES BRASIL SISTEMAS PARA TRATAMENTO DE EFLUENTES LTDA', NULL, '14666357000118', TRUE, 85),
    ('175', 'VIBROMAQ SISTEMA DE VENTILAÇÃO LTDA', NULL, '07135696000102', TRUE, 117),
    ('17825', 'FINATI COMERCIO E INDUSTRIA DE EQUIPAMENTOS ELETROMECANICOS', NULL, '33223551000173', TRUE, 45),
    ('17846', 'ROMAO TECNOLOGIAS INDUSTRIAIS LTDA', NULL, '02807845000119', TRUE, 91),
    ('189', 'VETTOR TORRES DE RESFRIAMENTO LTDA', NULL, '02825612000149', TRUE, 116),
    ('19348', 'IBS TECNOLOGIA S.A.', NULL, '88979067000160', TRUE, 59),
    ('194', 'FOCKINK INDUSTRIAS ELETRICAS LTDA', NULL, '03021334000130', TRUE, 49),
    ('1960', 'EXTRUAL LIMITADA', NULL, NULL, TRUE, 42),
    ('19660', 'FERRAZ MAQUINAS E ENGENHARIA LTDA', NULL, '43490424000194', TRUE, 44),
    ('2019', 'MACOFREN TECNOLOGIAS QUIMICAS LTDA', NULL, '19031125000107', FALSE, 72),
    ('20388', 'HIDROPEL HIDROGEOLOGIA E PERFURAÇÕES LTDA.', NULL, '91851154000142', TRUE, 56),
    ('204', 'NG METALURGICA S.A.', NULL, '01939979000392', TRUE, 82),
    ('208', 'ALFA LAVAL LTDA', NULL, '43474212000385', TRUE, 10),
    ('21093', 'MESSIAS FERNANDES NETO', NULL, NULL, TRUE, 77),
    ('21239', 'UWT DO BRASIL INSTRUMENTOS DE MEDIÇÃO LTDA', NULL, '37111162000107', TRUE, 113),
    ('21558', 'TRANE TECHNOLOGIES LATIN AMERICA B.V.', NULL, NULL, TRUE, 110),
    ('217', 'ENGEDELTA ENGENHARIA E CONSTRUÇÃO LTDA', NULL, '72244114000350', TRUE, 40),
    ('21711', 'GRANFINALE SISTEMAS AGRÍCOLAS LTDA.', NULL, '04703272000109', TRUE, 53),
    ('21729', 'AEROAR INDUSTRIA MECÂNICA LTDA', NULL, '79387858000100', TRUE, 6),
    ('21820', 'GEORGE & FILHO INDUSTRIA COMERCIO E PRESTAÇÃO DE SERVIÇOS LTDA', NULL, '00908685000179', TRUE, 51),
    ('21964', 'AGUIA SOLUCOES TECNOLOGICAS EM ACO INOX LTDA', NULL, '08236152000108', TRUE, 9),
    ('22078', 'HCI HIDRAULICA CONEXOES INDUSTRIAIS LTDA', NULL, '62312426000723', TRUE, 54),
    ('22230', 'BERMAD BRASIL INDUSTRIA DE VALVULAS LTDA.', NULL, '01000334000128', TRUE, 19),
    ('22321', 'LS EQUIPAMENTOS DE FORÇA E SEGURANÇA LTDA', NULL, '40950413000151', TRUE, 71),
    ('22775', 'SUPPORT PAINÉIS ELÉTRICOS LTDA', NULL, '52085108000128', TRUE, 103),
    ('261', 'PROMOEN EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '00250937000115', TRUE, 88),
    ('26961', 'METALURGICA VARB INDUSTRIA E COMERCIO LTDA', NULL, '43830462000149', TRUE, 79),
    ('2707', 'GH DO BRASIL INDUSTRIA E COMERCIO LTDA', NULL, '04407579000162', TRUE, 52),
    ('271', 'SULZER PUMPS WASTEWATER BRASIL LTDA', NULL, '77153260001365', TRUE, 102),
    ('27114', 'AURA VISION LTDA', NULL, '55046154000106', TRUE, 17),
    ('27371', 'SIEMENS BRASIL LTDA', NULL, '34776007000200', TRUE, 99),
    ('2778', 'BRASIL SUL MICROFUSAO DE ACOS EIRELI', NULL, '17825586000126', TRUE, 21),
    ('279', 'VAN AARSEN INTERNATIONAL B.V.', NULL, NULL, TRUE, 114),
    ('281', 'FLUID-QUIP, INC.', NULL, NULL, TRUE, 47),
    ('282', 'JIANGSU GRAND DRYING AND CONCENTRATING EQUIPMENT CO., LTD', NULL, NULL, TRUE, 64),
    ('2930', 'MKG EQUIPAMENTOS LTDA', NULL, '05115921000113', TRUE, 80),
    ('29453', 'CONDUZ KABEL IND. COM. LTDA.', NULL, '45182736000166', TRUE, 26),
    ('3026', 'FLOTTWEG SE', NULL, NULL, TRUE, 46),
    ('3043', 'KSB BRASIL LTDA', NULL, '60680873000114', TRUE, 69),
    ('31006', 'ENERGY SUBSTATION SERVICES LTDA', NULL, '20714257000112', TRUE, 39),
    ('315', 'ATLAS COPCO BRASIL LTDA', NULL, '57029431004780', TRUE, 16),
    ('316', 'KOCH-GLITSCH, LP', NULL, NULL, TRUE, 68),
    ('3189', 'AUTI AUTOMACAO INDUSTRIAL LTDA', NULL, '02322570000123', TRUE, 18),
    ('32211', 'MECVISO INDUSTRIA E COMERCIO LTDA', NULL, '60237213000163', TRUE, 74),
    ('327', 'SAUR EQUIPAMENTOS S.A.', NULL, '92253095000173', TRUE, 94),
    ('3307', 'AMPLA INDUSTRIA METALURGICA LTDA', NULL, '89660757000115', TRUE, 12),
    ('3557', 'MELFEX INDUSTRIA E COMERCIO DE MATERIAIS ELETRICOS EIRELI', NULL, '06746643000165', TRUE, 75),
    ('358', 'AMBORETTO BOMBAS LTDA', NULL, '01705998000354', TRUE, 11),
    ('365', 'HITER CONTROLS ENGENHARIA LTDA', NULL, '24743237000120', TRUE, 57),
    ('3721', 'ADVANTECH BRASIL LTDA', NULL, '03800074000281', TRUE, 4),
    ('3766', 'MARTIN SPROCKET & GEAR BRASIL ENGRENAGENS LTDA', NULL, '11755916000178', TRUE, 73),
    ('3843', 'DRIVETECH SOLUÇÕES TECNOLOGICAS LTDA', NULL, '09183422000114', TRUE, 32),
    ('393', 'ABB LTDA', NULL, '61074829008701', TRUE, 2),
    ('394', 'ENGEVAL ARARAS-ENGENHARIA DE VALVULAS E EQUIPAMENTOS LTDA', NULL, '00200093000106', TRUE, 41),
    ('4155', 'ADVANTECH BRASIL LTDA', NULL, '03800074000109', TRUE, 5),
    ('418', 'SPIRAX SARCO IND COM LT', NULL, '61193074000186', TRUE, 101),
    ('445', 'HIDRO-THERMAL CORP', NULL, NULL, TRUE, 55),
    ('448', 'INDUSTRIAL DUJUA MAQUINAS E EQUIPAMENTOS LTDA', NULL, '82091018000100', TRUE, 61),
    ('451', 'GARDNER DENVER NASH BRASIL INDÚSTRIA E COMÉRCIO DE BOMBAS LT', NULL, '60882776000104', TRUE, 50),
    ('4590', 'TWT EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '08974695000114', TRUE, 112),
    ('466', 'ANDRITZ SEPARATION IND. E COM. DE EQUIPS. DE FILTRAÇÃO LTDA', NULL, '06349916000138', TRUE, 13),
    ('473', 'BRAY CONTROLS INDÚSTRIA DE VÁLVULAS LTDA', NULL, '06979206000191', TRUE, 22),
    ('4765', 'SENGEFAR SISTEMAS INDUSTRIAIS LTDA', NULL, '29688761000160', TRUE, 97),
    ('4967', 'CONEX ELETROMECANICA INDUSTRIA E COMERCIO LTDA', NULL, '54601612000169', TRUE, 27),
    ('499', 'VEOLIA TECNOLOGIAS E SOLUCOES PARA TRATAMENTO DE AGUAS LTDA', NULL, '28234708000126', TRUE, 115),
    ('506', 'SEEMIL SERVICE LTDA', NULL, '21372291000119', TRUE, 96),
    ('5142', 'INTEGRASUL SOLUÇÕES EM INFORMÁTICA LTDA', NULL, '06249471000114', TRUE, 63),
    ('52051', 'TMSA - TECNOLOGIA EM MOVIMENTAÇÃO SA', NULL, '92782705000126', TRUE, 108),
    ('527', 'DURCON EQUIPAMENTOS INDUSTRIAIS LIMITADA', NULL, '57948762000131', TRUE, 35),
    ('5381', 'DW SERVICE AUTOMACAO INDUSTRIAL LTDA', NULL, '36099089000132', TRUE, 36),
    ('573', 'PROMINENT BRASIL LTDA', NULL, '38875381000125', TRUE, 87),
    ('63', 'CALDEMA-EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '45372893000134', TRUE, 23),
    ('6734', 'IBAM INDÚSTRIA BRASILEIRA DE ARTEFATOS DE METAIS EIRELI', NULL, '29478545000190', TRUE, 58),
    ('692', 'WILLY INSTRUMENTOS DE MEDICAO E CONTROLE LTDA.', NULL, '07645541000116', TRUE, 122),
    ('70', 'DELL COMPUTADORES DO BRASIL LTDA', NULL, '72381189001001', TRUE, 31),
    ('707', 'ZEOCHEM LLC', NULL, NULL, TRUE, 123),
    ('709', 'AGIMIX SOLUCOES E EQUIPAMENTOS INDUSTRIAIS LTDA', NULL, '14295834000186', TRUE, 8),
    ('7303', 'LALLEMAND BRASIL LTDA', NULL, '49979842000126', TRUE, 70),
    ('7316', 'TECNO AIR VENTILADORES INDUSTRIAIS E SISTEMAS EIRELI', NULL, '32676885000130', TRUE, 105),
    ('732', 'SANDPLAST COMERCIO DE PLÁSTICOS LTDA', NULL, '17586131000103', TRUE, 92),
    ('751', 'EMERSON PROCESS MANAGEMENT LTDA', NULL, '43213776000100', TRUE, 37),
    ('7543', 'TELBRA INDÚSTRIA E COMERCIO LTDA', NULL, '03578248000122', TRUE, 106),
    ('7593', 'FAST INDÚSTRIA E COMÉRCIO LTDA', NULL, '00771598000112', TRUE, 43),
    ('763', 'DRYERATION - INDUSTRIA, COMERCIO E PROJETOS LTDA', NULL, '87744546000305', FALSE, 33),
    ('7729', 'INDUSUL INDUSTRIA DE TRANSFORMADORES LTDA', NULL, '08018660000101', TRUE, 62),
    ('780', 'NETZSCH DO BRASIL INDUSTRIA E COMERCIO LTDA', NULL, '82749987000106', TRUE, 81),
    ('79843', 'RKF SOLUCOES EM ENERGIA LTDA', NULL, '26510017000263', TRUE, 90),
    ('80134', 'FMW FÖRDERANLAGEN', NULL, NULL, TRUE, 48),
    ('8033', 'KELVION INTERCAMBIADORES LTDA', NULL, '47344197000140', TRUE, 66),
    ('81589', 'CITROTEC INDUSTRIA E COMERCIO LTDA', NULL, '03727941000110', TRUE, 24),
    ('862', 'COMIL SILOS E SECADORES LTDA', NULL, '76061480000162', TRUE, 25),
    ('887', 'SHIMADZU DO BRASIL COMERCIO LTDA.', NULL, '58752460000156', TRUE, 98),
    ('913', 'KIDDE BRASIL LTDA', NULL, '66220047000179', TRUE, 67),
    ('927', 'JUNIOR FLEX INDUSTRIA E PARTICIPAÇÕES LTDA', NULL, '02600415000121', TRUE, 65),
    ('967', 'REDLANDS DO BRASIL INDUSTRIA E COMERCIO EIRELI', NULL, '01203871000175', TRUE, 89),
    ('9793', 'TSPRO FABRICACAO DISTRIBUICAO E REPRESENTACAO DE EQUIPAMENTO', NULL, '13108393000101', TRUE, 111);

CREATE TEMP TABLE _supplier_alias_stage (
    corporate_code varchar(20) NOT NULL,
    alias varchar(200) NOT NULL,
    source_row integer NOT NULL,
    PRIMARY KEY (corporate_code, alias),
    UNIQUE (alias)
) ON COMMIT DROP;

INSERT INTO _supplier_alias_stage (corporate_code, alias, source_row)
VALUES
    ('1061', 'TECNAL', 104),
    ('1065', 'SARTORIUS', 93),
    ('10794', 'TRANE', 109),
    ('12903', 'MERC - COMERCIO DE MATERIAIS PARA CONSTRUCAO LTDA', 76),
    ('1303', 'ENDRESS HAUSER', 38),
    ('135', 'WEG', 120),
    ('13974', 'AGI', 7),
    ('1402', 'BERMO', 20),
    ('1469', 'SCANJET', 95),
    ('161', 'APLUS', 14),
    ('16905', 'APS COMPONENTES', 15),
    ('175', 'VIBROMAQ', 117),
    ('189', 'VETTOR', 116),
    ('1960', 'EXTRUAL', 42),
    ('19660', 'FERRAZ', 44),
    ('204', 'NG METALÚRGICA', 82),
    ('208', 'ALFA LAVAL', 10),
    ('21239', 'UWT INSTRUMENTOS', 113),
    ('21558', 'TRANE TECHNOLOGIES LATIN AMERICA B.V.', 110),
    ('21820', 'GEORGE & FILHO', 51),
    ('21964', 'AGUIA INOX', 9),
    ('21964', 'Aguia Solucoes Tecnologicas em Aco Inox LTDA', 9),
    ('271', 'SULZER', 102),
    ('279', 'VAN AARSEN', 114),
    ('281', 'FLUID QUIP', 47),
    ('282', 'JIANGSU GRAND', 64),
    ('3026', 'FLOTTWEG', 46),
    ('3043', 'KSB', 69),
    ('315', 'ATLAS COPCO', 16),
    ('32211', 'MECVISO', 74),
    ('3307', 'AMPLA', 12),
    ('365', 'HITER', 57),
    ('3766', 'MARTIN SPROCKET', 73),
    ('393', 'ABB', 2),
    ('445', 'HIDRO-THERMAL', 55),
    ('451', 'GARDNER NASH', 50),
    ('4590', 'TWT', 112),
    ('466', 'ANDRITZ', 13),
    ('4765', 'SENGEFAR', 97),
    ('4967', 'CONEX', 27),
    ('499', 'VEOLIA', 115),
    ('52051', 'TMSA', 108),
    ('573', 'PROMINENT', 87),
    ('63', 'CALDEMA', 23),
    ('709', 'AGIMIX', 8),
    ('7303', 'LALLEMAND', 70),
    ('7316', 'TECNO AIR', 105),
    ('732', 'SANDPLAST PLASTICOS', 92),
    ('751', 'EMERSON PROCESS', 37),
    ('7593', 'FAST', 43),
    ('780', 'NETZSCH', 81),
    ('8033', 'KELVION', 66),
    ('81589', 'CITROTEC', 24),
    ('887', 'SHIMADZU', 98),
    ('913', 'KIDDE', 67),
    ('967', 'REDLANDS', 89);

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
