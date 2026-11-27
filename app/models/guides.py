from decimal import Decimal

from tortoise import fields, models

from app.models.enums import GuideStatus, GuideType, PromptKind


class PromptVersion(models.Model):
    """프롬프트 버전 (ERD prompt_versions, NFR-017). 가이드·챗봇·검증 기록이 이 버전을 가리킵니다."""

    id = fields.BigIntField(primary_key=True)
    kind = fields.CharEnumField(PromptKind, max_length=30)
    version = fields.CharField(max_length=20)
    content = fields.TextField(description="시스템 프롬프트 + 출력 항목 템플릿")
    model = fields.CharField(max_length=50, description="개발 Haiku, 배포 모델은 고도화 주간에 결정")
    temperature = fields.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.10"), description="0.1~0.2 고정"
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "prompt_versions"
        unique_together = (("kind", "version"),)


class Guide(models.Model):
    """처방 하나의 복약·생활습관 가이드 (ERD guides, GUIDE-001~005).

    실패해도 행을 지우지 않고 status=failed, content=NULL로 둡니다(행 없음 = 아직 시작 안 함).
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="guides", on_delete=fields.CASCADE
    )
    prescription: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.Prescription", related_name="guides", on_delete=fields.CASCADE
    )
    guide_type = fields.CharEnumField(GuideType, max_length=20)
    status = fields.CharEnumField(GuideStatus, max_length=30, default=GuideStatus.GENERATING)
    content = fields.JSONField(null=True, description="약별 항목 JSON. 생성 중·실패 시 NULL")
    prompt_version: fields.ForeignKeyNullableRelation[PromptVersion] = fields.ForeignKeyField(
        "models.PromptVersion", related_name="guides", null=True, on_delete=fields.SET_NULL
    )
    input_hash = fields.CharField(max_length=64, null=True, db_index=True, description="[2차] 동일 입력 캐싱 키")
    used_default_profile = fields.BooleanField(default=False, description="건강 프로필 없이 생성")
    is_outdated = fields.BooleanField(default=False, description="처방 수정 시 true")
    regen_date = fields.DateField(null=True, description="[2차] 다시 만들기 집계 날짜 (KST)")
    regen_count = fields.IntField(default=0, description="[2차] '다시 만들기'만 셈, 하루 3회")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "guides"
        unique_together = (("prescription", "guide_type"),)
