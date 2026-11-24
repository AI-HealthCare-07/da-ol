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
    "item_name" VARCHAR(200) NOT NULL,
    "item_name_norm" VARCHAR(200) NOT NULL,
    "ingredient_name" VARCHAR(300),
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
    "drug_name_raw" VARCHAR(200) NOT NULL,
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
    "eJztXWtz4rjS/iuufJlJnWzWgLmlaj4wgcxwJiGphOzuOcuWS5ZF4hOwWWxmJu/W7G9/1Z"
    "LvloltIDZZvqSIrJbl7tatL4/+OppbOpnZpz2yNPDj0Zn015GJ5oT+iD05kY7QYhGUQ4GD"
    "tBmrioI6mu0sEXZo6RTNbEKLdGLjpbFwDMukpeZqNoNCC9OKhvkQFK1M488VUR3rgTiPZE"
    "kf/P4HLTZMnXwntvfv4kmdGmSmR7pq6PBuVq46zwtWNjSdC1YR3qap2Jqt5mZQefHsPFqm"
    "X9swHSh9ICZZIodA885yBd2H3rnf6X0R72lQhXcxRKOTKVrNnNDnZuQBtkzgH+2NzT7wAd"
    "7yU72mtJVOo6V0aBXWE7+k/YN/XvDtnJBxYDQ++sGeIwfxGoyNAd++kqUNXUow7/wRLcXc"
    "C5HEWEg7Hmehx7B1PPQKAiYGirMlLs7Rd3VGzAcHFLzebK7h2S+92/PPvdv3tNYxfI1FlZ"
    "nr+Mh9VOfPgLEBI2Fo5GCiW30/GViT5QwMpLVSGcieRRlI3+gQPgajTPz33fVIzMQQSYyR"
    "9yb9wN91Azsn0sywnT+qydY1XISvhk7PbfvPWZh57696v8X5en55/ZFxwbKdhyVrhTXwkf"
    "IYpszpU2jwQ4GG8NM3tNTVxBOrbqXVTT6a1+fxEmSiB8Yr+GL4PncRubfZhJ5YXFj52qVl"
    "RWvYmVaWo8lKb3XwZIVbuiy9H9z2pa91idEfn0q0mLQV/2+rrtAirdOk9ZE+7dCidpv+1b"
    "oYQ91ODR7gaZM22mzCAw3LnADoiEIboSVQhDsdeHOjw95BKJ3WnmLWILwDN3GL/q1rtCmt"
    "jqGpOlFOj2Iqsn+93/J6/dF4eENLdrdebzTadbnR6jSVdrvZkf21O/lo3SL+cfgJ1vHIiH"
    "95YX9CT8hSRWxOX5TCNNtZmQry+kio7cHoCGvtaeQJKGxd16ECBhpEGrQ27spyfLiVttCR"
    "OTJmecTiExSSicvxzVc1gVBgdgBp4FqNTSsNvQvzBsw3dNaBIoQ1HepqslfXn6Fg8sFt1C"
    "wimJ1s4UwDP7HfOWQTpil3yNT/rjGGdmW2WHRrNRgE0yYfEUw8WkNhNWrwV1Yk/h+TCWIV"
    "9A4TE8GFZJJlrNTTh0o9MVJyC2MTQWx1nOhdBXRflvla3GSiYKtpuwP/dOpNPgagGlFg8u"
    "piWRrdX14WYX0zC+ub6axvJlivGUvnUaWri0AAfVoqFkCUKiYGKHaMOTn1nr8pgawRQL83"
    "HsTYSz9d5/vepG4PzNWcsXdIX4BMTBJsDqj/cZpey7Ygr1mP45pu2OpiaU2NGaEcni9mBP"
    "iW3Jta1owgM2VzmtJETDoabWNX59DUA1FWAbXYiaDD1+YmOwXQ1WBj3f94fX0ZOcZ+HMa2"
    "sqP7q48DKjMmMlrJcCI73EBQtvFgrhacmwUHTqyJ17O+uI0y8cdE9GkwGtz2Ls8kt8rEvO"
    "ndjmnZmbRAS8fkA738xdjTcGNOD/jqaplrCyskLnny+r1ONR3XO38UW3GzLbnr1twEi6nW"
    "Oiu7sHL71K+o1wg7xlciUOve+Xj4y+BM4hUm5q/D8ef+be/X0Zn0zXAe9SX6ZlZDsfmpF2"
    "FMbFt1rCcisIaPyfcUw4SYuiqqzSbzpsJPyvC3qWw8pY8Hv43XWybnz+6Ty+vRJ6963Fy5"
    "Rgjk+8JYEltFAmtw391FZpBGtJl1u1H4UeW5Z500hleDu3Hv6iYiEthywpN6RBxe6ftWbH"
    "j4jUgwTCX4V/rv9WgQtyn79cb/PYI+oZVjqab1TUV6+Ou9Yq9IIOklmdI2H4uOtwT5YcAV"
    "GnAeHzcdceJ2DkOuGkPOX3ALyDdOWymZ0gEmg0dCr/ETTV1nXg+5dioxs2+7zY4zbcSLZX"
    "7o8f0jYKOcrGRZa8MBSK6BK6XFKGSk80oFTMhvSXPwkoAcC+hNlHILWlOG15t+g35tzp5d"
    "pd0Tybrja61gVwu9oGCjlAfBlipY1vkcHv6Q+53oBkYzlTJrNSfAl4QefHSbuPhyS2bIEc"
    "f8uG78K95c322tmmL/4emyVxqIP2znCBrfkCk3oab2mCO0GD0RdWY9bMiPIWvo0nrYY2bo"
    "yJg9q9OZ9c2NSinOjj40dcFa2jOG7DJQyJtCbhCLo0gEDEWen6wLHPKmNnVBq2aOIMJN3P"
    "QiazSFOU71hozd3eS/2L9dHm+juM4ML1Yn+kIetMNqaRqL0IG6Ne70lj7AL73Z6Z5IN/0L"
    "yRQ0+4GV0iqiUKGqdlMQE/S7Lwk2FsACbFpHfxxChSoSKuRJJMHlVBaHKF7m807nsiMW1t"
    "DxQ1C4oxFjLRr8ww6HcOSDahnNzluJvA64bC2NB8OkO668UQ0JwnJtXVUKup7TE8Yah6CY"
    "nxGikgOwj5hD7Of/LcjDicR/L0z6ky5qM7qfhlo/L/RpMQ/VtmNCmAfPNv6PqNqzQwSbn9"
    "T5QkBZ8rzxygkYMSY+Ivsxj8pGiHalstlDM90IzGknuum4+9z7qd5sFVHWlpJBWVtKqrLC"
    "IwGfF8jJz2ePaD9zM3bjmLZWS0zU/BuFJOHrjftaHt2FDbXS4cGrwr0z3f0enwh2yhAO31"
    "WkWjmbCh5PkVfNo1RlL4HX57eBET4kHQhT8vdwLdQViSUpj2JL5Q7GjIWXqkO+C+yr6c7N"
    "ME3poX1aF1wruI7AmylrjP8trOyNhxOYuVlETbSFV4yqWRBTB1YmxXIzGPWHo09nkltlYv"
    "avR4MzeqY3ycS86A0vB31oki5kepGhsP3wGp2weMgCnoYoZcUcjykLiTeTaRiWBjo4OiLr"
    "SszDGPgt/3keRt8YldfMEyPcs/PEK5h8Em6hJNOTHL+wlsR4ML+Q58TU+AYdP7R4ib75Ns"
    "e4TtGv5XMQWzJ6d+e9/uDoRzn5s3E+CyzjAlGkG8eF/r8i9nE/1Qtj2JxpuN71zHDupq7Z"
    "hnw8Xabler2OfTt0ogvMFO22Bgl+ksDM/SHyJimUaNYWptRWvbuHHNrqGsZpPzdKNwjTl3"
    "3Kurkd3J3fDm/Gw+sR3T2GPNMT82Z4eakORr8MLq9v6F5yYcxmKjG/kpnF+17+JnIPI+NX"
    "i5mFdHcXHpXF/c3lNV1K6EbdqzQx6SlY5Vt5OHXw7TyUeVt6KOXb+ol5fj26GN5eQTGVw9"
    "RYzqF08NvN8BbKeBBmRbb/j5a9MJwCbo8E4V66PXaSQW7Y9oqei/JmZ8bIqpSeGV6LwRz3"
    "M3PltWUvUhMKT7lNqOlbg/ixyctnbgexmnAqgyW2Vt/4PCXI3VygpU3ZSGdQ+KgE/9OtOw"
    "nC0k089HzaZLxjh9gWWHU0xJP7GYchHNYTBDzmCf0yQxbBEiDMMKHsuaGIm0P5Tl/V6WYs"
    "v6kipYlKRUeKgkb+JTVC5octyGffzA+LpQW5QvRzwdK3LGaoSm2kUjYrupsIDiMc8CGYQW"
    "PR84moCpYq3GVAQl020wIIkI8sgTBhKBJsHtEUpEiAKoF1mf1fq7HZuON5WaBMbsIhS2Z9"
    "QRxniDWoN+qdSC99/CLwsoRDOt5DLYXb1VjLrS6L/ED68T9PjQ9x+m8inFsgWG9/X0S0Md"
    "oqzUZ5TXdVl2WmUQpYbrnt3CGig407h417ZYsAVnLbtz18wupxOatRO6RAeQ3a0RjRTcPd"
    "Y4Hb+8PRfPHu4lSSdN5dm2Rs0T9bzyfZ6gm9Dps4AHhjO7xpjR0jdN+3CXu43GBJYkbnyR"
    "VYrh6ORDkCUH6yNjeA1sjh8mjr8XNurREKqIfGjk8l4nkPcFuR+Y6UWzIYIh5/pCvMUaA3"
    "ccfPSfVReSZRPD0sI8ydEzyymQflY7Gbo3pdPLg2quvaMBwyV23yZx6LbJimdHhQBvLpqj"
    "I9LEpcbWEmQt3wMZH+nTK7lqJXBNWQsTGvNTxCVH4EsIxrAcM7xSA8M1nG62ss43WBZdxj"
    "E92DL+eFGOxTlu2xg36gGQTNw+TN+vb+GKbXBvaBnPm8TI8g2LPfet5tvix3Oxlteq8hG5"
    "OepXQDwitya3+SdEe288xDILCWs6kHLKquNc11TtQaNYahpxQfIo1MYmisEUNDhLM/XyDz"
    "OQ/7QyQHJ5wP4zydGhhhASPTPUBhmj3h5Gs7Y1Y2eFLyBk5HqQ6sFbKWHkcxWqXgGqxxW0"
    "bJDswVMtc2dKLS8U2wCEojnbtxugN7xex16HM6xOf0KGkJDodrGJygPLBY7Aa3VcuFqI0d"
    "vF/APvaoisEdbzVlBTW6vqvQNYkEYMbMrYkQ92EWNloJz+DbQzkuBK9bIVjdKqUtcusHcf"
    "DjGv9ZSnZBknTDeKmtBnJojbbsHfLAzhe45XFNY152NgJade5sR5tD1wkCoRiPeIanWFkz"
    "RMhGmyj7yD3o3f1H7d/efzqTCLKf2cF7Yt4Mbq+GY0i5Ws4NpxpGJDex9iUYt7VZudmR3F"
    "7d2ZAw7mGkhezbPO+2i3kUIHgmuCEEogB3oemwyDm4wMrIicpfGHlqGp0cOkJT/x6skYVA"
    "7sIOOBUsfFsEdBvS5l57e9NlMVekpUfipbbrftsdrpdNzi1TN9zvEQB7hSucrEf2suGqDb"
    "du3ssBMWMZvx8sGlDMAl0hNSeElRV504l0Nej/JMud4zXX922vfSGYVkKp2XCZWc4BVatK"
    "HjZPIgkup4NlBBTlo2oFuiy9r51I9ROpcXp6mjG0ctswF/4A2SgdK9lKyQH4MGNLH6R36d"
    "NEPES/qSjcaf+uGtvQOREZDLKJw6MtWQgfbwe9Lxe9O7rB15YEPU2R7UzMy/vR+eczabYy"
    "8ePE7A9H7EIe3TArcx+PNZ3axFHnhrnKB8aVJCw02+xgwx/OwmUlLI3E5G60cmYe2i5Zfk"
    "Uz9ZGemfJwOUlYLpfzrp5b4yAcIlUN2Ubh9M1oC2XbCNYl0l5fXAzPh3CZlwWePgNu8xoN"
    "Bv079fzz4PwLbZIQ3VbxI8FP1ZhFPICuxyWyc7nkE4SlJ7NFIVd4RFqwrsLvbtNPbIHMti"
    "IS2Ikr2U0M1FKc8i+PkEgDZQ+Q2/vLwZm0XM0IXUYvr+giOptPzPs7WEC9oOzyFZ9FRfsZ"
    "EjlNO0niKlz1GNkqukC4/Mpl1yHi5/nxiBWWuIWhlqzJQW6W3mx1yrb2pAHys/Nu7hSKtB"
    "YO+RQ58imEZocNkysK2NMqlBZwEku0SFOz4lkXNrif6ES6ceaFTe7cpvaLxfG9+OvfQ1Ga"
    "3//1rbO+iqQYZ8Mq9IJtNqK4WUyzWleH1AQdJY2m8VUrYjr1X+RZTrvHp+zyAm6EhYXv3T"
    "dCnnT0/C5AX4LbCpgDCXOfEkuHJy2RTbc6HUu5WSFsP2b9R89c3w+m4KqYgn2RFNzeh+nL"
    "3t3/Ohh86ff+cya5yjsxoWQw6vMSYuoT8wpOxnM4EI/v6VHAWcH9vwNWgz4df76nZY+riX"
    "lxO6QvXhoT8643PpNs5NBf95TWXlXkbmCMZng1Y15yL0M6KsBLi1YZp6dgJ+nT/OyvjgcR"
    "skUECQNbc/dCvjQ7AHiBaMLs64D3nTcA+WVxo04MduPLmWQ9Vd0OhPT/rezCap6groyShy"
    "/mdV1aDLgX1F1ikSQ1FjxS47FTADg+1XaAybvRUODsVekuz3RRobNa6ZKUFbooWRTM42F+"
    "NSceFD/Cms4RZiJANEWGTSNbOs2abJq4ZB6W1mqhPpFc6TQRosrIgwUR6h0lWAtkdomSpj"
    "VaLF0YCxKdqiGFw2WmbwL9JnnXYuRwUwAhXEB+sPnlwgmPny43NPglYryqx/is1j6hdlUJ"
    "MTyCFiIw6cTRRNJNOokrcTOBZgSo17VY0FukveNTiSPTue4LtvZ7QQBC0JEgRFVpymyHUO"
    "tyQAvu92DbO9R0XRl+M27GtMxCDWqNmhBGYy86fQDWqK6tZ7N8iOqkQlD1ZqDTE/OqN7qH"
    "kAY60ax4xFb5x9UDqvQOohD4BKcVQJYWkFYlnWQb6ZaCjJA9tE7R9dr4SgQWqt75ePjL4E"
    "ziFSbmYMSw6YnpodeXPtznZC4IpF5zxatbfy8H905SIQ8AsW/iiMwYc7B9vD3BJmwfB6zY"
    "7e/aK3LrXHyB2QQFb5uonJUwOR1ge8kWYXvLyXmtEFcFQVNZrkH0MHkzalv+SxCrOgdkt3"
    "6m35R4NxjzN0ZVdGvGTKaFLxg0PU3NZtQMcsMLWjYn0evDkzg0NYZGKrYm8rcLM4p3+aqD"
    "FbHs/ciaiDEP8VOloy7PyTdBWLYdcSK4aBOyEny4aL3tXgzj4VFUDFLWTXQSIxK+mB9VDU"
    "hCgRQkLxIG8qEkb8pIXuaVNeP7FdCcwOGWVwwRouqNBT+kAgCr2YVrU7aYgzuI+X7ev+Px"
    "Sc13BQWRSQ5rxCCUAppbK9G2qU+wMUezNaIIKOMGB0566jZRSTvdOhPx4Hx41bt83zlpxB"
    "KaPC4rYlbS7udXaI9oL+2btWy+izWui4Rx85lW2gwaItJCZWKyovkCEQ+yjozZczWs85x5"
    "bjx4ik8kxbacoCyZ9dCV2bMKveFxcCwPo6lg6d3V9ehk/Pm+EPDG9kPeOOd8kAHodx50gj"
    "TykpEgyFeyfFZN3p+YALJmBOwAvsBWF2QJSpGDwwm6kllb+1s5jSDITLzLG90L7yHniAHS"
    "eHe+aHWUdRe+ZZ6zSzRzO6GjVFVC64zfSixNEjcenzBB4JZ/v4N7KWarrrDZf/OMbIET27"
    "EgEkI8aacrdoSobKCq2t+NVklaalqOMX1WiQlflRdBIEn8iggCvskkuu1oBKH57pyA3Vuc"
    "FdDIroal69HP1xcXG+viFtEBDo7tN+H/PDi236hgE45t+qGOYa6ofKZLa14M0CO9jZJ3Wc"
    "HR7Z3ngMFNDf7y6/IS1nq/mrvguxeXddpehaq5biMGDDA25/agB0Sl485tC1C3HPZHHTsb"
    "YeIcQkY2gcPZQrxCzqtdK+RhP1mLgrMmfiE+k2yBi969r3s4hWR2vAfTZ4rT/YXFdsvK+u"
    "ow6GUtsVkFlL43yRIkkTLbRLHOiwfz7HH+XYpe7zuqf9XUuXzErSrp3C7zMwOeCGKZIgxL"
    "D2KKCSgT0hbHsHIvx8Ia8/O3sK9JLFnRix0KtX98Kvm3ntZJx0t31Gta08OR9BMgMQtPgk"
    "i0BrMgRWEmOQAH7govMq9a97JfwUB74VufPfQvFxElDsX111GgI+FAT78JqE++w2tsNum7"
    "uuQqiavE3hg7YpWp4Nk/Pw5RW2VFbYU1IKvXIkxTJZ8FvzEI4Wkw9OA6dQ5VxzKTSQfihd"
    "xHMq5Jf0ts7Ck+WkjoGQ93OT6RvtyNd+HKiA24hABeADBKklcGwcgPCpKRHBeFGI+QcZsF"
    "cGkyhufytL3W98ey0KuB+vUWgrwi8nKxx9vuXWVRqRSJJdh+SJdhq8hWAZIstxsrTlo+DH"
    "YE8Eus8OkbizygRq/j3trDPOMFoedLDjYWvzphMOoPR5/gJkVWZWKOe18GIzpb0l2cOTGv"
    "hnd3kHk8N2y7KqnHrGsFnFBhui24oCoV7Fglj5P32Wt9iQcn8ZvwJSYFWxmEsNLu6SnV53"
    "S4jOG1+H5IB982dw85yFvIQV47NZTjaaowO/NdEJK+zm3DU5rTEVSdazDiTH0ZhzGLq22X"
    "hv4+pGpczKxvzHycvFoj9Phk7c0aUFGdsprZ7zwOrHXR69BwW4mllISPxT4hdzLpTRaUzL"
    "1QaKo0gssuwp1y77qotbmxXa51xfckl92nCT1sclsle5um+Y42F5ARjDf+P3ApRyg8W8HS"
    "B6hC+G1Z7WY33VHgrSSBYf+QYn0w1pdkrA95y069L2EWSiUBSBq0kTHtNJ+1ng9NVi/3pj"
    "ZJW3bMZyhunk1DkxBMffzOHwbvqrtOkaoHGBq2Sncsjjjz6SW7cJiyAmbhcHJDHUYLz7v2"
    "AHbZJQS6jDru5F8lG/DCgvepCHYiIgt9+lE7Qfh6x0B5nQyiYyIjs7d+qfzBKPg2jYIHW8"
    "m2F4WDrWSneG3bP3z++H+WGE/z"
)
