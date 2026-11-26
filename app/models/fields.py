import datetime
from typing import Any

from tortoise import fields
from tortoise.models import Model


class LocalTimeField(fields.TimeField):
    """시간대 없는 시각(Postgres TIME) 필드.

    Tortoise 기본 TimeField는 Postgres에서 TIMETZ로 만들어지고 읽을 때 시간대를 붙입니다.
    복용 시각(08:00 등)은 KST 벽시계 시각이라 ERD대로 TIME으로 저장하고,
    unique 인덱스(intake_logs.scheduled_time 등)에서 시간대가 섞이지 않게 naive time 그대로 다룹니다.
    """

    SQL_TYPE = "TIME"

    class _db_postgres:  # noqa: N801 - Tortoise가 DB별 타입을 찾는 이름
        SQL_TYPE = "TIME"

    def to_python_value(self, value: Any) -> datetime.time | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.time.fromisoformat(value)
        return value.replace(tzinfo=None)

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> datetime.time | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.time.fromisoformat(value)
        self.validate(value)
        return value.replace(tzinfo=None)
