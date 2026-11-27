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


class VectorField(fields.Field[list[float]]):
    """pgvector의 vector(1536) 필드 (rag_chunks.embedding).

    Tortoise에는 vector 타입이 없어서 LocalTimeField처럼 SQL 타입만 정해 둡니다.
    DB에는 '[0.1,0.2,...]' 글자로 주고받고, 파이썬에서는 float 목록으로 씁니다.
    임베딩 모델(text-embedding-3-small)이 1536차원이라 고정합니다. 모델을 바꾸면 차원부터 확인하세요.
    """

    SQL_TYPE = "vector(1536)"

    class _db_postgres:  # noqa: N801 - Tortoise가 DB별 타입을 찾는 이름
        SQL_TYPE = "vector(1536)"

    def to_db_value(self, value: Any, instance: type[Model] | Model) -> str | None:
        if value is None:
            return None
        return "[" + ",".join(str(float(x)) for x in value) + "]"

    def to_python_value(self, value: Any) -> list[float] | None:
        if value is None or isinstance(value, list):
            return value
        return [float(x) for x in str(value).strip("[]").split(",") if x]
