-- Catálogo corporativo de descrições dos Work Packages.
-- Pode ser executado diretamente no SQL Editor do Neon antes ou depois do deploy.
-- É idempotente: não cria WPs, não altera obra/contexto e só atualiza códigos existentes.

BEGIN;

ALTER TABLE work_package
    ADD COLUMN IF NOT EXISTS description VARCHAR(500);

WITH descriptions(code, description) AS (
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
UPDATE work_package AS wp
SET description = descriptions.description
FROM descriptions
WHERE upper(btrim(wp.code)) = descriptions.code;

-- Este arquivo reproduz integralmente a migration 0015. Registra a versão
-- somente quando o banco ainda está exatamente na migration anterior.
UPDATE alembic_version
SET version_num = '0015_wp_descriptions'
WHERE version_num = '0014_supplier_history';

COMMIT;

-- Conferência: mostra todas as WPs existentes e o fallback esperado pela tela.
SELECT
    pc.name AS obra,
    wp.code,
    COALESCE(NULLIF(btrim(wp.description), ''), 'WP sem descrição') AS description
FROM work_package AS wp
JOIN project_context AS pc ON pc.id = wp.project_context_id
ORDER BY pc.name, wp.code;
