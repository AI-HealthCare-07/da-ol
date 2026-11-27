from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "rag_documents" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "source_type" VARCHAR(20) NOT NULL,
    "title" VARCHAR(300) NOT NULL,
    "publisher" VARCHAR(100),
    "published_at" DATE,
    "source_url" VARCHAR(500),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "drug_id" BIGINT REFERENCES "drugs" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "rag_documents"."source_type" IS '1차는 guideline만';
COMMENT ON COLUMN "rag_documents"."title" IS '가이드 하단 출처(문서명)';
COMMENT ON COLUMN "rag_documents"."publisher" IS '출처 표시용 기관명';
COMMENT ON COLUMN "rag_documents"."published_at" IS '자료 발표일';
COMMENT ON COLUMN "rag_documents"."drug_id" IS 'source_type=drug_info일 때만 (1차 미사용)';
COMMENT ON TABLE "rag_documents" IS '근거 문서 1건 (ERD rag_documents, GUIDE-003). 조각과 임베딩은 rag_chunks.';
        CREATE TABLE IF NOT EXISTS "rag_chunks" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "chunk_no" INT NOT NULL,
    "section" VARCHAR(200),
    "content" TEXT NOT NULL,
    "embedding" vector(1536) NOT NULL,
    "embedding_model" VARCHAR(50) NOT NULL DEFAULT 'text-embedding-3-small',
    "search_text" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "rag_document_id" BIGINT NOT NULL REFERENCES "rag_documents" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_rag_chunks_rag_doc_c43ea6" UNIQUE ("rag_document_id", "chunk_no")
);
COMMENT ON COLUMN "rag_chunks"."chunk_no" IS '문서 안 순서(1부터)';
COMMENT ON COLUMN "rag_chunks"."section" IS '조각이 속한 제목';
COMMENT ON COLUMN "rag_chunks"."content" IS '원문 조각 글';
COMMENT ON COLUMN "rag_chunks"."embedding" IS 'content의 임베딩 (text-embedding-3-small, 1536차원)';
COMMENT ON COLUMN "rag_chunks"."search_text" IS '[2차] 키워드 검색(Kiwi+BM25)용 글. 1차는 NULL';
COMMENT ON TABLE "rag_chunks" IS '문서 조각 + 임베딩 (ERD rag_chunks). 검색은 SQL로 `ORDER BY embedding <=> 질문벡터 LIMIT 5`.';
        CREATE TABLE IF NOT EXISTS "prompt_versions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "kind" VARCHAR(30) NOT NULL,
    "version" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "model" VARCHAR(50) NOT NULL,
    "temperature" DECIMAL(3,2) NOT NULL DEFAULT 0.10,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "uid_prompt_vers_kind_cca1db" UNIQUE ("kind", "version")
);
COMMENT ON COLUMN "prompt_versions"."kind" IS 'GUIDE_MEDICATION: guide_medication\nGUIDE_LIFESTYLE: guide_lifestyle\nCHAT: chat\nPARSE_CONDITION: parse_condition\nPARSE_DOCUMENT: parse_document\nSCOPE_CLASSIFY: scope_classify\nVERIFY: verify';
COMMENT ON COLUMN "prompt_versions"."content" IS '시스템 프롬프트 + 출력 항목 템플릿';
COMMENT ON COLUMN "prompt_versions"."model" IS '개발 Haiku, 배포 모델은 고도화 주간에 결정';
COMMENT ON COLUMN "prompt_versions"."temperature" IS '0.1~0.2 고정';
COMMENT ON TABLE "prompt_versions" IS '프롬프트 버전 (ERD prompt_versions, NFR-017). 가이드·챗봇·검증 기록이 이 버전을 가리킵니다.';
        CREATE TABLE IF NOT EXISTS "guides" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "guide_type" VARCHAR(20) NOT NULL,
    "status" VARCHAR(30) NOT NULL DEFAULT 'generating',
    "content" JSONB,
    "input_hash" VARCHAR(64),
    "used_default_profile" BOOL NOT NULL DEFAULT False,
    "is_outdated" BOOL NOT NULL DEFAULT False,
    "regen_date" DATE,
    "regen_count" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "prescription_id" BIGINT NOT NULL REFERENCES "prescriptions" ("id") ON DELETE CASCADE,
    "prompt_version_id" BIGINT REFERENCES "prompt_versions" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_guides_prescri_3e2a32" UNIQUE ("prescription_id", "guide_type")
);
CREATE INDEX IF NOT EXISTS "idx_guides_input_h_ab23f0" ON "guides" ("input_hash");
COMMENT ON COLUMN "guides"."guide_type" IS 'MEDICATION: medication\nLIFESTYLE: lifestyle';
COMMENT ON COLUMN "guides"."status" IS 'GENERATING: generating\nVERIFYING: verifying\nCOMPLETED: completed\nCOMPLETED_WITH_REPLACEMENTS: completed_with_replacements\nFAILED: failed';
COMMENT ON COLUMN "guides"."content" IS '약별 항목 JSON. 생성 중·실패 시 NULL';
COMMENT ON COLUMN "guides"."input_hash" IS '[2차] 동일 입력 캐싱 키';
COMMENT ON COLUMN "guides"."used_default_profile" IS '건강 프로필 없이 생성';
COMMENT ON COLUMN "guides"."is_outdated" IS '처방 수정 시 true';
COMMENT ON COLUMN "guides"."regen_date" IS '[2차] 다시 만들기 집계 날짜 (KST)';
COMMENT ON COLUMN "guides"."regen_count" IS '[2차] ''다시 만들기''만 셈, 하루 3회';
COMMENT ON TABLE "guides" IS '처방 하나의 복약·생활습관 가이드 (ERD guides, GUIDE-001~005).';
        CREATE TABLE IF NOT EXISTS "chat_sessions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(20),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "chat_sessions"."title" IS '[2차] 첫 질문 앞 20자';
COMMENT ON COLUMN "chat_sessions"."updated_at" IS '최근 대화 순 정렬';
COMMENT ON COLUMN "chat_sessions"."deleted_at" IS '[2차]';
COMMENT ON TABLE "chat_sessions" IS '챗봇 대화방 (ERD chat_sessions, CHAT-001·003).';
        CREATE TABLE IF NOT EXISTS "chat_messages" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "role" VARCHAR(20) NOT NULL,
    "message_type" VARCHAR(30) NOT NULL DEFAULT 'normal',
    "status" VARCHAR(20) NOT NULL DEFAULT 'completed',
    "content" TEXT NOT NULL,
    "is_recommended_question" BOOL NOT NULL DEFAULT False,
    "counts_toward_quota" BOOL NOT NULL DEFAULT True,
    "check_result" JSONB,
    "verify_status" VARCHAR(20) NOT NULL DEFAULT 'not_needed',
    "correction_note" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "prompt_version_id" BIGINT REFERENCES "prompt_versions" ("id") ON DELETE SET NULL,
    "session_id" BIGINT NOT NULL REFERENCES "chat_sessions" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_chat_messag_session_fb3c4b" ON "chat_messages" ("session_id", "created_at");
COMMENT ON COLUMN "chat_messages"."role" IS 'USER: user\nASSISTANT: assistant';
COMMENT ON COLUMN "chat_messages"."message_type" IS 'NORMAL: normal\nEMERGENCY_PHYSICAL: emergency_physical\nEMERGENCY_SELF_HARM: emergency_self_harm\nOUT_OF_SCOPE: out_of_scope';
COMMENT ON COLUMN "chat_messages"."status" IS 'STREAMING: streaming\nCOMPLETED: completed\nFAILED: failed';
COMMENT ON COLUMN "chat_messages"."content" IS '최대 500자(질문). 암호화';
COMMENT ON COLUMN "chat_messages"."is_recommended_question" IS '추천 질문 버튼';
COMMENT ON COLUMN "chat_messages"."counts_toward_quota" IS '[2차] 응급·범위 밖·실패는 false';
COMMENT ON COLUMN "chat_messages"."check_result" IS 'check_full() 반환값. 회원 질문 행은 NULL';
COMMENT ON COLUMN "chat_messages"."verify_status" IS '[2차] VERI-007';
COMMENT ON TABLE "chat_messages" IS '챗봇 메시지 (ERD chat_messages, CHAT-001~006). LLM 요청엔 최근 10턴만.';
        CREATE TABLE IF NOT EXISTS "llm_call_logs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "purpose" VARCHAR(20) NOT NULL,
    "model" VARCHAR(50) NOT NULL,
    "input_tokens" INT NOT NULL,
    "output_tokens" INT NOT NULL,
    "cache_read_tokens" INT NOT NULL DEFAULT 0,
    "latency_ms" INT NOT NULL,
    "success" BOOL NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "prompt_version_id" BIGINT REFERENCES "prompt_versions" ("id") ON DELETE SET NULL,
    "user_id" BIGINT REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_llm_call_lo_created_a865d0" ON "llm_call_logs" ("created_at");
COMMENT ON COLUMN "llm_call_logs"."purpose" IS 'GUIDE: guide\nCHAT: chat\nPARSE: parse\nVERIFY: verify\nCLASSIFY: classify';
COMMENT ON COLUMN "llm_call_logs"."cache_read_tokens" IS 'Prompt Caching 효과 확인';
COMMENT ON TABLE "llm_call_logs" IS 'LLM 호출 기록 (ERD llm_call_logs, NFR-006 비용 관리). 프롬프트·답변 본문과 개인정보는 저장하지 않습니다.';
        -- [수동 추가] rag_chunks 임베딩 검색용 HNSW 인덱스 (코사인 거리). Tortoise 모델로는 표현할 수 없어 직접 추가
        CREATE INDEX IF NOT EXISTS "idx_rag_chunks_embedding_hnsw" ON "rag_chunks" USING hnsw ("embedding" vector_cosine_ops);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "rag_chunks";
        DROP TABLE IF EXISTS "rag_documents";
        DROP TABLE IF EXISTS "chat_messages";
        DROP TABLE IF EXISTS "chat_sessions";
        DROP TABLE IF EXISTS "guides";
        DROP TABLE IF EXISTS "llm_call_logs";
        DROP TABLE IF EXISTS "prompt_versions";"""


MODELS_STATE = (
    "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"
    "G44RZ6R0gzCquJajjmv56/8BDhgJmQ=="
)
