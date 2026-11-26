from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- [수동 추가] pgvector(RAG 임베딩), pg_trgm(약 이름 유사도 검색)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "kakao_id" VARCHAR(100) NOT NULL UNIQUE,
    "email" VARCHAR(255),
    "nickname" VARCHAR(20) NOT NULL UNIQUE,
    "name" VARCHAR(50),
    "birth_date" DATE,
    "gender" VARCHAR(10),
    "is_profile_completed" BOOL NOT NULL DEFAULT False,
    "signup_type" VARCHAR(20) NOT NULL DEFAULT 'general',
    "profile_image_url" VARCHAR(500),
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "kakao_access_token" TEXT,
    "kakao_access_expires_at" TIMESTAMPTZ,
    "kakao_refresh_token" TEXT,
    "kakao_refresh_expires_at" TIMESTAMPTZ,
    "withdrawn_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "users"."kakao_id" IS '카카오 회원번호. 회원 식별 기준';
COMMENT ON COLUMN "users"."email" IS '카카오에서 동의한 경우에만 저장';
COMMENT ON COLUMN "users"."nickname" IS '2~10자. 중복 시 무작위 4자리 부여';
COMMENT ON COLUMN "users"."name" IS '추가 정보 입력 전까지 NULL';
COMMENT ON COLUMN "users"."birth_date" IS '추가 정보 입력 전까지 NULL';
COMMENT ON COLUMN "users"."gender" IS '추가 정보 입력 전까지 NULL';
COMMENT ON COLUMN "users"."is_profile_completed" IS '추가 정보 입력 완료 여부';
COMMENT ON COLUMN "users"."signup_type" IS 'GENERAL: general\nPARTNER: partner';
COMMENT ON COLUMN "users"."profile_image_url" IS '[2차]';
COMMENT ON COLUMN "users"."status" IS 'ACTIVE: active\nWITHDRAWN: withdrawn';
COMMENT ON COLUMN "users"."kakao_access_token" IS '[2차] 암호화';
COMMENT ON COLUMN "users"."kakao_access_expires_at" IS '[2차]';
COMMENT ON COLUMN "users"."kakao_refresh_token" IS '[2차] 암호화';
COMMENT ON COLUMN "users"."kakao_refresh_expires_at" IS '[2차]';
COMMENT ON COLUMN "users"."withdrawn_at" IS '탈퇴 시각. 30일 재가입 제한·영구 삭제 기준';
COMMENT ON TABLE "users" IS '회원 (ERD v2 users). 카카오 로그인만 제공하므로 비밀번호 컬럼이 없습니다.';
CREATE TABLE IF NOT EXISTS "medical_documents" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "doc_type" VARCHAR(20) NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'uploaded',
    "hospital_name" VARCHAR(100),
    "issued_date" DATE,
    "parsed_result" TEXT,
    "image_delete_due_at" TIMESTAMPTZ NOT NULL,
    "processing_started_at" TIMESTAMPTZ,
    "fail_reason" VARCHAR(30),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "confirmed_at" TIMESTAMPTZ,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "medical_documents"."doc_type" IS 'PRESCRIPTION: prescription\nPILL_ENVELOPE: pill_envelope';
COMMENT ON COLUMN "medical_documents"."status" IS 'UPLOADED: uploaded\nOCR_DONE: ocr_done\nOCR_FAILED: ocr_failed\nCONFIRMED: confirmed\nEXPIRED: expired';
COMMENT ON COLUMN "medical_documents"."issued_date" IS '처방일 / 조제일. 복용 시작일 기본값';
COMMENT ON COLUMN "medical_documents"."parsed_result" IS '확인 화면용 구조화 결과 JSON. 마스킹 후 암호화';
COMMENT ON COLUMN "medical_documents"."image_delete_due_at" IS '업로드 + 3시간';
COMMENT ON COLUMN "medical_documents"."processing_started_at" IS 'OCR 처리 시작 시각. 문서 종류를 다시 고른 뒤 90초 넘게 안 끝나면 실패 처리하는 기준(채민 요청)';
COMMENT ON COLUMN "medical_documents"."fail_reason" IS 'ocr_failed일 때만 값: ocr_error / no_text / no_drug_found / structure_error / timeout (채민 요청)';
COMMENT ON TABLE "medical_documents" IS '업로드한 처방전·약봉투 (ERD v2 medical_documents). 한 번 업로드 = 처방 한 건.';
CREATE TABLE IF NOT EXISTS "document_pages" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "page_no" INT NOT NULL,
    "original_name" VARCHAR(255),
    "mime_type" VARCHAR(50) NOT NULL,
    "file_size_bytes" INT NOT NULL,
    "file_hash" VARCHAR(64) NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "source_page_no" INT NOT NULL DEFAULT 1,
    "image_path" VARCHAR(500) NOT NULL,
    "ocr_text" TEXT,
    "ocr_status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "deleted_at" TIMESTAMPTZ,
    "document_id" BIGINT NOT NULL REFERENCES "medical_documents" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_document_pa_documen_ea11b5" UNIQUE ("document_id", "page_no")
);
CREATE INDEX IF NOT EXISTS "idx_document_pa_file_ha_45cc7f" ON "document_pages" ("file_hash");
COMMENT ON COLUMN "document_pages"."page_no" IS '문서 전체 기준 순서';
COMMENT ON COLUMN "document_pages"."mime_type" IS 'image/jpeg, image/png, application/pdf';
COMMENT ON COLUMN "document_pages"."file_hash" IS '원본 파일 SHA-256';
COMMENT ON COLUMN "document_pages"."source_page_no" IS '원본 파일 안의 페이지 (PDF), 이미지는 1';
COMMENT ON COLUMN "document_pages"."image_path" IS 'OCR·원본 보기용 페이지 이미지';
COMMENT ON COLUMN "document_pages"."ocr_text" IS '마스킹 후 암호화';
COMMENT ON COLUMN "document_pages"."ocr_status" IS 'PENDING: pending\nDONE: done\nFAILED: failed';
COMMENT ON COLUMN "document_pages"."deleted_at" IS '원본 파일·변환 이미지 삭제 시각';
COMMENT ON TABLE "document_pages" IS '업로드 파일 + 페이지 (ERD v2 document_pages). 이미지 1장 = 1행, PDF n페이지 = n행.';
CREATE TABLE IF NOT EXISTS "drugs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "item_seq" VARCHAR(20) NOT NULL UNIQUE,
    "item_name" VARCHAR(500) NOT NULL,
    "item_name_norm" VARCHAR(500) NOT NULL,
    "ingredient_name" VARCHAR(500),
    "company" VARCHAR(100),
    "efficacy" TEXT,
    "usage_text" TEXT,
    "precautions" TEXT,
    "side_effects" TEXT,
    "storage_method" TEXT,
    "is_oral" BOOL,
    "image_url" VARCHAR(500),
    "data_fetched_at" DATE NOT NULL,
    "data_source" VARCHAR(20) NOT NULL,
    "source_updated_at" DATE,
    "is_otc" BOOL
);
CREATE INDEX IF NOT EXISTS "idx_drugs_item_na_f6c470" ON "drugs" ("item_name");
CREATE INDEX IF NOT EXISTS "idx_drugs_ingredi_aad869" ON "drugs" ("ingredient_name");
COMMENT ON COLUMN "drugs"."item_seq" IS '식약처 품목기준코드';
COMMENT ON COLUMN "drugs"."item_name" IS '상품명';
COMMENT ON COLUMN "drugs"."item_name_norm" IS 'normalize_drug_name()으로 정규화한 이름';
COMMENT ON COLUMN "drugs"."ingredient_name" IS '화면 표시용 성분명';
COMMENT ON COLUMN "drugs"."is_oral" IS '먹는 약 여부. 모르면 NULL';
COMMENT ON COLUMN "drugs"."data_fetched_at" IS '데이터를 받아 온 날';
COMMENT ON COLUMN "drugs"."data_source" IS 'EASY_DRUG: easy_drug\nPERMIT: permit';
COMMENT ON COLUMN "drugs"."source_updated_at" IS '식약처 쪽 마지막 수정일';
COMMENT ON COLUMN "drugs"."is_otc" IS '일반의약품 여부. 모르면 NULL';
COMMENT ON TABLE "drugs" IS '약 마스터 (ERD v2 drugs). e약은요 / 의약품 허가정보에서 사전 적재.';
CREATE TABLE IF NOT EXISTS "prescriptions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "source" VARCHAR(20) NOT NULL,
    "hospital_name" VARCHAR(100),
    "prescribed_date" DATE,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "memo" VARCHAR(500),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    "document_id" BIGINT UNIQUE REFERENCES "medical_documents" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "prescriptions"."source" IS 'OCR: ocr\nMANUAL: manual';
COMMENT ON COLUMN "prescriptions"."status" IS 'ACTIVE: active\nENDED: ended';
COMMENT ON COLUMN "prescriptions"."document_id" IS '수동 등록이면 NULL';
COMMENT ON TABLE "prescriptions" IS '처방 1건 (ERD v2 prescriptions). OCR 확정·수동 등록 모두 같은 저장 함수로 생성.';
CREATE TABLE IF NOT EXISTS "prescription_items" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "drug_name_raw" VARCHAR(500) NOT NULL,
    "source_text" VARCHAR(500),
    "dose_text" VARCHAR(50) NOT NULL,
    "dose_amount" DECIMAL(8,3),
    "dose_unit" VARCHAR(10),
    "cycle_type" VARCHAR(20),
    "cycle_weekdays" VARCHAR(30),
    "cycle_interval_weeks" INT,
    "times_per_day" INT,
    "start_date" DATE NOT NULL,
    "total_days" INT NOT NULL,
    "notify_enabled" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "continued_from_item_id" BIGINT REFERENCES "prescription_items" ("id") ON DELETE SET NULL,
    "drug_id" BIGINT REFERENCES "drugs" ("id") ON DELETE SET NULL,
    "prescription_id" BIGINT NOT NULL REFERENCES "prescriptions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "prescription_items"."drug_name_raw" IS '처방전에 적힌 약품명';
COMMENT ON COLUMN "prescription_items"."source_text" IS '처방전 원문 줄 (마스킹)';
COMMENT ON COLUMN "prescription_items"."dose_text" IS '처방전 표기 그대로 (''1정'')';
COMMENT ON COLUMN "prescription_items"."cycle_type" IS '[2차] 1차는 모두 daily';
COMMENT ON COLUMN "prescription_items"."cycle_weekdays" IS 'weekly_days 일 때 ''MON,THU''';
COMMENT ON COLUMN "prescription_items"."cycle_interval_weeks" IS 'every_n_weeks 일 때 n';
COMMENT ON COLUMN "prescription_items"."times_per_day" IS '1~4. 필요시 약만 NULL 가능';
COMMENT ON COLUMN "prescription_items"."start_date" IS '기본값 처방일, 없으면 오늘';
COMMENT ON COLUMN "prescription_items"."total_days" IS '1~365';
COMMENT ON COLUMN "prescription_items"."notify_enabled" IS '[3차] 약별 알림 ON/OFF';
COMMENT ON COLUMN "prescription_items"."continued_from_item_id" IS '[2차] ''이어서 먹는 약''이면 기존 약';
COMMENT ON COLUMN "prescription_items"."drug_id" IS '매칭 실패면 NULL';
COMMENT ON TABLE "prescription_items" IS '처방 1건 안의 먹는 약 1줄 (ERD v2 prescription_items).';
CREATE TABLE IF NOT EXISTS "dose_conditions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "slot_no" INT NOT NULL,
    "condition_type" VARCHAR(20),
    "meal" VARCHAR(20),
    "offset_minutes" INT,
    "interval_hours" INT,
    "time_basis" VARCHAR(20) NOT NULL,
    "source_phrase" VARCHAR(100),
    "parsed_by" VARCHAR(20) NOT NULL,
    "user_confirmed" BOOL NOT NULL DEFAULT False,
    "prescription_item_id" BIGINT NOT NULL REFERENCES "prescription_items" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_dose_condit_prescri_2a8472" UNIQUE ("prescription_item_id", "slot_no")
);
COMMENT ON COLUMN "dose_conditions"."slot_no" IS '회차 (1, 2, 3...)';
COMMENT ON COLUMN "dose_conditions"."condition_type" IS 'NULL = ''복용 조건 확인 필요''';
COMMENT ON COLUMN "dose_conditions"."meal" IS 'BREAKFAST: breakfast\nLUNCH: lunch\nDINNER: dinner';
COMMENT ON COLUMN "dose_conditions"."offset_minutes" IS '식전·식후 n분';
COMMENT ON COLUMN "dose_conditions"."time_basis" IS 'PRESCRIPTION: prescription\nOFFICIAL: official\nNEEDS_CHECK: needs_check';
COMMENT ON COLUMN "dose_conditions"."source_phrase" IS '변환 전 복용법 문구';
COMMENT ON COLUMN "dose_conditions"."parsed_by" IS 'RULE: rule\nLLM: llm\nUSER: user';
COMMENT ON COLUMN "dose_conditions"."user_confirmed" IS '확인 전에는 시간표 계산 안 함';
COMMENT ON TABLE "dose_conditions" IS '회차별 복용 조건 (ERD v2 dose_conditions, MED-008).';
CREATE TABLE IF NOT EXISTS "dose_schedules" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "day_type" VARCHAR(20) NOT NULL,
    "calculated_time" TIME,
    "status" VARCHAR(20) NOT NULL DEFAULT 'ok',
    "adjusted_time" TIME,
    "adjust_warning" VARCHAR(30),
    "group_key" VARCHAR(30),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dose_condition_id" BIGINT NOT NULL REFERENCES "dose_conditions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_dose_schedu_dose_co_ff15e8" UNIQUE ("dose_condition_id", "day_type")
);
COMMENT ON COLUMN "dose_schedules"."day_type" IS 'WEEKDAY: weekday\nWEEKEND: weekend\nMON: mon\nTUE: tue\nWED: wed\nTHU: thu\nFRI: fri\nSAT: sat\nSUN: sun';
COMMENT ON COLUMN "dose_schedules"."calculated_time" IS 'needs_check 이면 NULL';
COMMENT ON COLUMN "dose_schedules"."status" IS 'OK: ok\nNEEDS_CHECK: needs_check';
COMMENT ON COLUMN "dose_schedules"."adjusted_time" IS '[2차] 회원이 직접 바꾼 시각';
COMMENT ON COLUMN "dose_schedules"."adjust_warning" IS '[2차] 마지막 조정의 경고 종류';
COMMENT ON COLUMN "dose_schedules"."group_key" IS '[2차] 30분 이내 묶음 표시용';
COMMENT ON TABLE "dose_schedules" IS '맞춤 복용 시간표 (ERD v2 dose_schedules, MED-009). 1차는 ''weekday'' 한 행만 만듦.';
CREATE TABLE IF NOT EXISTS "intake_logs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "log_date" DATE NOT NULL,
    "scheduled_time" TIME,
    "dose_text" VARCHAR(50) NOT NULL,
    "is_as_needed" BOOL NOT NULL DEFAULT False,
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "taken_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dose_condition_id" BIGINT REFERENCES "dose_conditions" ("id") ON DELETE SET NULL,
    "prescription_item_id" BIGINT NOT NULL REFERENCES "prescription_items" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_intake_logs_prescri_4a3380" UNIQUE ("prescription_item_id", "log_date", "scheduled_time")
);
CREATE INDEX IF NOT EXISTS "idx_intake_logs_user_id_a7c87f" ON "intake_logs" ("user_id", "log_date");
COMMENT ON COLUMN "intake_logs"."log_date" IS '일과 기준 하루 (기상 ~ 다음 기상 전), KST';
COMMENT ON COLUMN "intake_logs"."scheduled_time" IS '그날 기준 복용 시각 스냅샷. 필요시 약은 NULL';
COMMENT ON COLUMN "intake_logs"."dose_text" IS '그날 용량 스냅샷';
COMMENT ON COLUMN "intake_logs"."is_as_needed" IS '[2차] 필요시 약 체크 기록용';
COMMENT ON COLUMN "intake_logs"."status" IS 'PENDING: pending\nTAKEN: taken\nMISSED: missed';
COMMENT ON TABLE "intake_logs" IS '복약 체크 기록 (ERD v2 intake_logs). 화단·통계·순응도 계산 원천.';
CREATE TABLE IF NOT EXISTS "daily_flowers" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "log_date" DATE NOT NULL,
    "flower_type_id" BIGINT,
    "is_rest_day" BOOL NOT NULL DEFAULT False,
    "points_awarded" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_daily_flowe_user_id_9df3a7" UNIQUE ("user_id", "log_date")
);
COMMENT ON COLUMN "daily_flowers"."log_date" IS '일과 기준 하루 (intake_logs.log_date 와 같은 기준)';
COMMENT ON COLUMN "daily_flowers"."flower_type_id" IS '[3차] 꽃 종류. 1차는 항상 NULL';
COMMENT ON COLUMN "daily_flowers"."is_rest_day" IS '[3차] 쉼표로 지킨 날';
COMMENT ON COLUMN "daily_flowers"."points_awarded" IS '[3차] 1차는 0';
COMMENT ON TABLE "daily_flowers" IS '하루 복용을 모두 체크하면 피는 꽃 (ERD v2 daily_flowers, MED-017·019).';
-- [수동 추가] Tortoise가 만들지 않는 제약·인덱스 (ERD v2 drugs, 11/24)
ALTER TABLE "drugs" ADD CONSTRAINT "chk_drugs_data_source" CHECK ("data_source" IN ('easy_drug', 'permit'));
CREATE INDEX IF NOT EXISTS "idx_drugs_item_name_norm_trgm" ON "drugs" USING GIN ("item_name_norm" gin_trgm_ops);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "t6kUPOhKtr0pHHQlO8Vr2/7l88f/A4Q35tA="
)
