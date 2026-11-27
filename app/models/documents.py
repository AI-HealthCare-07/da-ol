from tortoise import fields, models

from app.models.enums import DocumentStatus, DocumentType, OcrStatus


class MedicalDocument(models.Model):
    """업로드한 처방전·약봉투 (ERD v2 medical_documents). 한 번 업로드 = 처방 한 건."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="medical_documents", on_delete=fields.CASCADE
    )
    doc_type = fields.CharEnumField(DocumentType, max_length=20)
    status = fields.CharEnumField(DocumentStatus, max_length=20, default=DocumentStatus.UPLOADED)
    hospital_name = fields.CharField(max_length=100, null=True)
    issued_date = fields.DateField(null=True, description="처방일 / 조제일. 복용 시작일 기본값")
    parsed_result = fields.TextField(null=True, description="확인 화면용 구조화 결과 JSON. 마스킹 후 암호화")
    image_delete_due_at = fields.DatetimeField(description="업로드 + 3시간")
    processing_started_at = fields.DatetimeField(
        null=True,
        description="OCR 처리 시작 시각. 문서 종류를 다시 고른 뒤 90초 넘게 안 끝나면 실패 처리하는 기준(채민 요청)",
    )
    fail_reason = fields.CharField(
        max_length=30,
        null=True,
        description="ocr_failed일 때만 값: ocr_error / no_text / no_drug_found / structure_error / timeout (채민 요청)",
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    confirmed_at = fields.DatetimeField(null=True)
    step = fields.CharField(
        max_length=20, null=True, description="uploaded일 때 로딩 단계: reading / structuring (채민 요청)"
    )
    masked_lines = fields.TextField(
        null=True,
        description="가린 OCR 줄 JSON(page_no, line_idx, words[[글자, 신뢰도]]). 마스킹 후 암호화. 만료 시 NULL (채민 요청)",
    )
    pages: fields.ReverseRelation["DocumentPage"]

    class Meta:
        table = "medical_documents"


class DocumentPage(models.Model):
    """업로드 파일 + 페이지 (ERD v2 document_pages). 이미지 1장 = 1행, PDF n페이지 = n행."""

    id = fields.BigIntField(primary_key=True)
    document: fields.ForeignKeyRelation[MedicalDocument] = fields.ForeignKeyField(
        "models.MedicalDocument", related_name="pages", on_delete=fields.CASCADE
    )
    page_no = fields.IntField(description="문서 전체 기준 순서")
    original_name = fields.CharField(max_length=255, null=True)
    mime_type = fields.CharField(max_length=50, description="image/jpeg, image/png, application/pdf")
    file_size_bytes = fields.IntField()
    file_hash = fields.CharField(max_length=64, db_index=True, description="원본 파일 SHA-256")
    file_path = fields.CharField(max_length=500)
    source_page_no = fields.IntField(default=1, description="원본 파일 안의 페이지 (PDF), 이미지는 1")
    image_path = fields.CharField(max_length=500, description="OCR·원본 보기용 페이지 이미지")
    ocr_text = fields.TextField(null=True, description="마스킹 후 암호화")
    ocr_status = fields.CharEnumField(OcrStatus, max_length=20, default=OcrStatus.PENDING)
    deleted_at = fields.DatetimeField(null=True, description="원본 파일·변환 이미지 삭제 시각")

    class Meta:
        table = "document_pages"
        unique_together = (("document", "page_no"),)
