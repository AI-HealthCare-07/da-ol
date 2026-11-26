from tortoise import fields, models


class DailyFlower(models.Model):
    """하루 복용을 모두 체크하면 피는 꽃 (ERD v2 daily_flowers, MED-017·019).

    다 못 먹은 날은 행 없음 = 빈 흙.
    """

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="daily_flowers", on_delete=fields.CASCADE
    )
    log_date = fields.DateField(description="일과 기준 하루 (intake_logs.log_date 와 같은 기준)")
    # flower_types는 3차 테이블이라 아직 없어서 외래키 없이 둡니다. 1차는 항상 NULL = 기본 꽃
    flower_type_id = fields.BigIntField(null=True, description="[3차] 꽃 종류. 1차는 항상 NULL")
    is_rest_day = fields.BooleanField(default=False, description="[3차] 쉼표로 지킨 날")
    points_awarded = fields.IntField(default=0, description="[3차] 1차는 0")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "daily_flowers"
        unique_together = (("user", "log_date"),)
