-- Catálogo corporativo GLOBAL de Work Packages.
-- Execute inteiro no SQL Editor do Neon. É idempotente e preserva vínculos.
BEGIN;

ALTER TABLE work_package ADD COLUMN IF NOT EXISTS description VARCHAR(500);

CREATE TEMP TABLE wp_merge_map ON COMMIT DROP AS
SELECT id AS old_id,
       first_value(id) OVER (PARTITION BY upper(btrim(code)) ORDER BY active DESC, id) AS canonical_id
FROM work_package;

INSERT INTO equipment_work_package (id, equipment_id, work_package_id, created_at)
SELECT gen_random_uuid()::text, ewp.equipment_id, map.canonical_id, min(ewp.created_at)
FROM equipment_work_package AS ewp
JOIN wp_merge_map AS map ON map.old_id = ewp.work_package_id
WHERE map.old_id <> map.canonical_id
GROUP BY ewp.equipment_id, map.canonical_id
ON CONFLICT (equipment_id, work_package_id) DO NOTHING;

DELETE FROM equipment_work_package AS ewp USING wp_merge_map AS map
WHERE ewp.work_package_id = map.old_id AND map.old_id <> map.canonical_id;

UPDATE equipment AS equipment SET work_package_id = map.canonical_id
FROM wp_merge_map AS map
WHERE equipment.work_package_id = map.old_id AND map.old_id <> map.canonical_id;

DELETE FROM work_package AS wp USING wp_merge_map AS map
WHERE wp.id = map.old_id AND map.old_id <> map.canonical_id;

DROP INDEX IF EXISTS work_package_context_code_key;
DROP INDEX IF EXISTS work_package_context_id_idx;
ALTER TABLE work_package ALTER COLUMN project_context_id DROP NOT NULL;
UPDATE work_package SET code = upper(btrim(code)), project_context_id = NULL;
CREATE UNIQUE INDEX IF NOT EXISTS work_package_code_key ON work_package (code);

WITH catalog(code, description) AS (
    VALUES
        ('IP001', 'Locação de obra e topografia'),
        ('IP002', 'Sondagem SPT'),
        ('IP003', 'Canteiros e instalações provisórias'),
        ('CIV001', 'Terraplenagem'),
        ('CIV002', 'Execução civil do armazém (terraplenagem do armazém, estruturas pré moldadas, poços, túnel, saída de emergência, cobertura, pisos, taludes internos, esquadrias)'),
        ('CIV003', 'Bases de equipamentos, estruturas e suportes externos'),
        ('CIV004', 'Drenagem pluvial'),
        ('CIV005', 'Pisos e calçadas de concreto armado'),
        ('CIV006', 'Bases de eletrocentros'),
        ('CIV007', 'Pintura de sinalização horizontal (PCI, faixas de pedestre, caminho seguro)'),
        ('CAL001', 'Estruturas metálicas das torres, transportadores, galerias, guarda corpo, grades de piso e degraus'),
        ('CAL002', 'Montagem de equipamentos (elevadores, trippers, canalizações e transportadores)'),
        ('CAL003', 'Aeração e termometria'),
        ('CAL004', 'Estruturas metálicas diversas (cable rack, guarda corpo externo, fechamentos, tampas e grelhas)'),
        ('CAL005', 'Instalações de PCI (hidrantes, abrigos, extintores)'),
        ('CAL006', 'Locação de muncks, guindastes ou PTA'),
        ('CAL007', 'Remoção e reinstalação de telhas e desmontagens de transportadores'),
        ('CAL008', 'Rede de água em aço carbono para profilaxia'),
        ('ELT001', 'Instalações elétricas provisórias'),
        ('ELT002', 'Aterramento e SPDA'),
        ('ELT003', 'Infraestrutura elétrica'),
        ('ELT004', 'Iluminação geral'),
        ('ELT005', 'Execução de rede de média tensão'),
        ('INT001', 'Infraestrutura de instrumentação'),
        ('INT002', 'Infraestrutura de ar comprimido'),
        ('INT003', 'Execução de rede de fibra óptica primária, secundária, IEC e Wi-Fi'),
        ('EIA001', 'Execução de TAC'),
        ('AUT001', 'Infraestrutura de automação'),
        ('MEC001', 'Montagem de válvulas manuais e automáticas'),
        ('ECM001', 'Projetos de engenharia civil'),
        ('ECM002', 'Projetos de engenharia metal mecânica'),
        ('ECM003', 'Fornecimento de estruturas metálicas'),
        ('ECM004', 'Fornecimento de equipamentos (transportadores, elevadores, canalização, tripper)'),
        ('ECM005', 'Fornecimento de materiais para PCI (abrigos, válvulas, chaves, mangueiras, excluso EIA)'),
        ('EEI001', 'Projetos de engenharia elétrica, instrumentação e automação'),
        ('EEI002', 'Fornecimento de eletrocentro'),
        ('EEI003', 'Fornecimento de materiais e equipamentos EIA')
)
INSERT INTO work_package (id, project_context_id, code, name, description, active)
SELECT gen_random_uuid()::text, NULL, code, description, description, TRUE FROM catalog
ON CONFLICT (code) DO UPDATE SET
    description = EXCLUDED.description,
    name = CASE WHEN btrim(work_package.name) = '' OR upper(btrim(work_package.name)) = EXCLUDED.code
                THEN EXCLUDED.name ELSE work_package.name END,
    active = TRUE,
    project_context_id = NULL;

UPDATE alembic_version SET version_num = '0016_global_work_packages'
WHERE version_num IN ('0014_supplier_history', '0015_wp_descriptions');

COMMIT;

-- Conferência: deve retornar total_canonico = 37 e faltantes = 0.
WITH expected(code) AS (
    VALUES ('IP001'), ('IP002'), ('IP003'), ('CIV001'), ('CIV002'), ('CIV003'),
           ('CIV004'), ('CIV005'), ('CIV006'), ('CIV007'), ('CAL001'), ('CAL002'),
           ('CAL003'), ('CAL004'), ('CAL005'), ('CAL006'), ('CAL007'), ('CAL008'),
           ('ELT001'), ('ELT002'), ('ELT003'), ('ELT004'), ('ELT005'), ('INT001'),
           ('INT002'), ('INT003'), ('EIA001'), ('AUT001'), ('MEC001'), ('ECM001'),
           ('ECM002'), ('ECM003'), ('ECM004'), ('ECM005'), ('EEI001'), ('EEI002'),
           ('EEI003')
)
SELECT (SELECT count(*) FROM work_package WHERE code IN (SELECT code FROM expected)) AS total_canonico,
       (SELECT count(*) FROM expected WHERE code NOT IN (SELECT code FROM work_package)) AS faltantes;

SELECT code, name, description, active FROM work_package ORDER BY code;
