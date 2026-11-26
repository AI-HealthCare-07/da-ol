from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "refresh_tokens" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "token_hash" VARCHAR(255) NOT NULL UNIQUE,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "revoked_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "refresh_tokens"."token_hash" IS 'SHA-256 hex';
COMMENT ON COLUMN "refresh_tokens"."expires_at" IS '발급 + 14일';
COMMENT ON COLUMN "refresh_tokens"."revoked_at" IS '로그아웃·재발급(회전)·탈퇴 시 무효화';
COMMENT ON TABLE "refresh_tokens" IS '리프레시 토큰 (ERD v2 refresh_tokens). 원문은 쿠키로만 주고, DB에는 SHA-256 해시만 저장합니다(명세 4-1).';
        CREATE TABLE IF NOT EXISTS "user_consents" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "consent_type" VARCHAR(30) NOT NULL,
    "agreed" BOOL NOT NULL,
    "agreed_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_user_consen_user_id_9f8412" UNIQUE ("user_id", "consent_type")
);
COMMENT ON COLUMN "user_consents"."consent_type" IS 'TERMS: terms\nPRIVACY: privacy\nSENSITIVE_HEALTH: sensitive_health\nKAKAO_MESSAGE: kakao_message\nPARTNER_SHARE: partner_share\nPARTNER_RECEIVE: partner_receive';
COMMENT ON TABLE "user_consents" IS '약관·정보 동의 (ERD v2 user_consents). 동의 철회 시 agreed=False로 갱신합니다.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "user_consents";
        DROP TABLE IF EXISTS "refresh_tokens";"""


MODELS_STATE = (
    "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"
)
