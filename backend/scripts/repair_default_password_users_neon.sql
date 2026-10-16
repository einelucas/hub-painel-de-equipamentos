-- Reparo idempotente para o primeiro acesso de Lucas e Diego.
-- Execute uma vez no SQL Editor do Neon conectado ao banco usado pelo backend.
--
-- O script:
--   * exige que os dois registros já existam em "User";
--   * cria somente a credencial local ausente em "Account";
--   * preenche uma credencial existente apenas quando a senha está vazia;
--   * nunca sobrescreve uma senha que já tenha sido alterada.

BEGIN;

DO $$
DECLARE
    target_email text;
    default_password_hash text;
    target_user_id text;
    credential_id text;
    credential_password text;
BEGIN
    FOR target_email, default_password_hash IN
        SELECT *
        FROM (VALUES
            (
                'lucas.pinheiro@inpasa.com.br',
                'scrypt$16384$8$1$RVHyPM4iD/GSs5rrmAREag==$QSW7Aq3O7Amhd9j10uRLK7Cx03EgRYrnstMwi3m+NKKy5ZI6oC8HFjsA/0s7cT4ZHkAow8POkaLjUoqPoB/uBw=='
            ),
            (
                'diego.costa@inpasa.com.br',
                'scrypt$16384$8$1$UCu2he54cXKy5M11DixIYA==$/eKzN5vPACV86aznfVjF3+b4R63sWGykf8s4GfZatBnufGZ6NDNuxHi8Dmy2+AVV0HqX3QGIClBDy7i017hnJw=='
            )
        ) AS seed(email, password_hash)
    LOOP
        SELECT u.id
        INTO target_user_id
        FROM "User" AS u
        WHERE lower(trim(u.email)) = target_email
        LIMIT 1;

        IF target_user_id IS NULL THEN
            RAISE EXCEPTION 'Usuário % não encontrado em User; nenhuma alteração foi aplicada.', target_email;
        END IF;

        UPDATE "User"
        SET
            email = target_email,
            "emailVerified" = true,
            active = true,
            "authProvider" = CASE
                WHEN "externalUserId" IS NULL THEN 'LOCAL'
                ELSE "authProvider"
            END,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE id = target_user_id;

        SELECT a.id, a.password
        INTO credential_id, credential_password
        FROM "Account" AS a
        WHERE a."userId" = target_user_id
          AND a."providerId" = 'credential'
        LIMIT 1;

        IF credential_id IS NULL THEN
            INSERT INTO "Account" (
                id,
                "userId",
                "accountId",
                "providerId",
                password,
                "createdAt",
                "updatedAt"
            ) VALUES (
                gen_random_uuid()::text,
                target_user_id,
                target_user_id,
                'credential',
                default_password_hash,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            );
        ELSIF credential_password IS NULL OR credential_password = '' THEN
            UPDATE "Account"
            SET password = default_password_hash, "updatedAt" = CURRENT_TIMESTAMP
            WHERE id = credential_id;
        END IF;

        target_user_id := NULL;
        credential_id := NULL;
        credential_password := NULL;
    END LOOP;
END $$;

COMMIT;

-- Deve retornar duas linhas com has_password = true.
SELECT
    u.email,
    u.active,
    u."authProvider",
    (a.password IS NOT NULL AND a.password <> '') AS has_password
FROM "User" AS u
JOIN "Account" AS a
  ON a."userId" = u.id
 AND a."providerId" = 'credential'
WHERE lower(trim(u.email)) IN (
    'lucas.pinheiro@inpasa.com.br',
    'diego.costa@inpasa.com.br'
)
ORDER BY u.email;
