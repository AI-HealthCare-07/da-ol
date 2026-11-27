from tortoise import fields, models

from app.models.enums import LlmPurpose


class LlmCallLog(models.Model):
    """LLM 호출 기록 (ERD llm_call_logs, NFR-006 비용 관리). 프롬프트·답변 본문과 개인정보는 저장하지 않습니다."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.User", related_name="llm_call_logs", null=True, on_delete=fields.SET_NULL
    )
    purpose = fields.CharEnumField(LlmPurpose, max_length=20)
    model = fields.CharField(max_length=50)
    prompt_version: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.PromptVersion", related_name="llm_call_logs", null=True, on_delete=fields.SET_NULL
    )
    input_tokens = fields.IntField()
    output_tokens = fields.IntField()
    cache_read_tokens = fields.IntField(default=0, description="Prompt Caching 효과 확인")
    latency_ms = fields.IntField()
    success = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True, db_index=True)

    class Meta:
        table = "llm_call_logs"
