from tortoise import fields, models

from app.models.enums import (
    CycleType,
    DayType,
    DoseConditionType,
    MealType,
    ParsedBy,
    PrescriptionSource,
    PrescriptionStatus,
    ScheduleStatus,
    TimeBasis,
)
from app.models.fields import LocalTimeField


class Prescription(models.Model):
    """처방 1건 (ERD v2 prescriptions). OCR 확정·수동 등록 모두 같은 저장 함수로 생성."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="prescriptions", on_delete=fields.CASCADE
    )
    document: fields.OneToOneNullableRelation = fields.OneToOneField(
        "models.MedicalDocument",
        related_name="prescription",
        null=True,
        on_delete=fields.SET_NULL,
        description="수동 등록이면 NULL",
    )
    source = fields.CharEnumField(PrescriptionSource, max_length=20)
    hospital_name = fields.CharField(max_length=100, null=True)
    prescribed_date = fields.DateField(null=True)
    status = fields.CharEnumField(PrescriptionStatus, max_length=20, default=PrescriptionStatus.ACTIVE)
    memo = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    items: fields.ReverseRelation["PrescriptionItem"]

    class Meta:
        table = "prescriptions"


class PrescriptionItem(models.Model):
    """처방 1건 안의 먹는 약 1줄 (ERD v2 prescription_items)."""

    id = fields.BigIntField(primary_key=True)
    prescription: fields.ForeignKeyRelation[Prescription] = fields.ForeignKeyField(
        "models.Prescription", related_name="items", on_delete=fields.CASCADE
    )
    drug: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.Drug",
        related_name="prescription_items",
        null=True,
        on_delete=fields.SET_NULL,
        description="매칭 실패면 NULL",
    )
    drug_name_raw = fields.CharField(max_length=500, description="처방전에 적힌 약품명")
    source_text = fields.CharField(max_length=500, null=True, description="처방전 원문 줄 (마스킹)")
    dose_text = fields.CharField(max_length=50, description="처방전 표기 그대로 ('1정')")
    dose_amount = fields.DecimalField(max_digits=8, decimal_places=3, null=True)
    dose_unit = fields.CharField(max_length=10, null=True)
    cycle_type = fields.CharEnumField(CycleType, max_length=20, null=True, description="[2차] 1차는 모두 daily")
    cycle_weekdays = fields.CharField(max_length=30, null=True, description="weekly_days 일 때 'MON,THU'")
    cycle_interval_weeks = fields.IntField(null=True, description="every_n_weeks 일 때 n")
    times_per_day = fields.IntField(null=True, description="1~4. 필요시 약만 NULL 가능")
    start_date = fields.DateField(description="기본값 처방일, 없으면 오늘")
    total_days = fields.IntField(description="1~365")
    continued_from_item: fields.ForeignKeyNullableRelation["PrescriptionItem"] = fields.ForeignKeyField(
        "models.PrescriptionItem",
        related_name="continued_items",
        null=True,
        on_delete=fields.SET_NULL,
        description="[2차] '이어서 먹는 약'이면 기존 약",
    )
    notify_enabled = fields.BooleanField(default=True, description="[3차] 약별 알림 ON/OFF")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    conditions: fields.ReverseRelation["DoseCondition"]

    class Meta:
        table = "prescription_items"


class DoseCondition(models.Model):
    """회차별 복용 조건 (ERD v2 dose_conditions, MED-008)."""

    id = fields.BigIntField(primary_key=True)
    prescription_item: fields.ForeignKeyRelation[PrescriptionItem] = fields.ForeignKeyField(
        "models.PrescriptionItem", related_name="conditions", on_delete=fields.CASCADE
    )
    slot_no = fields.IntField(description="회차 (1, 2, 3...)")
    condition_type = fields.CharEnumField(
        DoseConditionType, max_length=20, null=True, description="NULL = '복용 조건 확인 필요'"
    )
    meal = fields.CharEnumField(MealType, max_length=20, null=True)
    offset_minutes = fields.IntField(null=True, description="식전·식후 n분")
    interval_hours = fields.IntField(null=True)
    time_basis = fields.CharEnumField(TimeBasis, max_length=20)
    source_phrase = fields.CharField(max_length=100, null=True, description="변환 전 복용법 문구")
    parsed_by = fields.CharEnumField(ParsedBy, max_length=20)
    user_confirmed = fields.BooleanField(default=False, description="확인 전에는 시간표 계산 안 함")

    schedules: fields.ReverseRelation["DoseSchedule"]

    class Meta:
        table = "dose_conditions"
        unique_together = (("prescription_item", "slot_no"),)


class DoseSchedule(models.Model):
    """맞춤 복용 시간표 (ERD v2 dose_schedules, MED-009). 1차는 'weekday' 한 행만 만듦."""

    id = fields.BigIntField(primary_key=True)
    dose_condition: fields.ForeignKeyRelation[DoseCondition] = fields.ForeignKeyField(
        "models.DoseCondition", related_name="schedules", on_delete=fields.CASCADE
    )
    day_type = fields.CharEnumField(DayType, max_length=20)
    calculated_time = LocalTimeField(null=True, description="needs_check 이면 NULL")
    status = fields.CharEnumField(ScheduleStatus, max_length=20, default=ScheduleStatus.OK)
    adjusted_time = LocalTimeField(null=True, description="[2차] 회원이 직접 바꾼 시각")
    adjust_warning = fields.CharField(max_length=30, null=True, description="[2차] 마지막 조정의 경고 종류")
    group_key = fields.CharField(max_length=30, null=True, description="[2차] 30분 이내 묶음 표시용")
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dose_schedules"
        unique_together = (("dose_condition", "day_type"),)
