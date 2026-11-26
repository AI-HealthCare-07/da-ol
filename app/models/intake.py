from tortoise import fields, models
from tortoise.indexes import Index

from app.models.enums import IntakeStatus
from app.models.fields import LocalTimeField


class IntakeLog(models.Model):
    """복약 체크 기록 (ERD v2 intake_logs). 화단·통계·순응도 계산 원천."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="intake_logs", on_delete=fields.CASCADE
    )
    prescription_item: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.PrescriptionItem", related_name="intake_logs", on_delete=fields.CASCADE
    )
    dose_condition: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.DoseCondition", related_name="intake_logs", null=True, on_delete=fields.SET_NULL
    )
    log_date = fields.DateField(description="일과 기준 하루 (기상 ~ 다음 기상 전), KST")
    scheduled_time = LocalTimeField(null=True, description="그날 기준 복용 시각 스냅샷. 필요시 약은 NULL")
    dose_text = fields.CharField(max_length=50, description="그날 용량 스냅샷")
    is_as_needed = fields.BooleanField(default=False, description="[2차] 필요시 약 체크 기록용")
    status = fields.CharEnumField(IntakeStatus, max_length=20, default=IntakeStatus.PENDING)
    taken_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "intake_logs"
        # scheduled_time = NULL(필요시 기록)은 Postgres에서 서로 다른 값으로 보아 하루 여러 번 저장 가능
        unique_together = (("prescription_item", "log_date", "scheduled_time"),)
        # Index는 필드 이름이 아니라 컬럼 이름을 받으므로 외래키는 user_id로 적습니다.
        indexes = (Index(fields=("user_id", "log_date")),)
