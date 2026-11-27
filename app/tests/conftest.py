import asyncio
import os
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from tortoise import Tortoise, connections, generate_config
from tortoise.contrib.test import finalizer, initializer

from app.core import config
from app.core.db.databases import TORTOISE_APP_MODELS

TEST_BASE_URL = "http://test"
TEST_DB_LABEL = "models"
TEST_DB_TZ = "Asia/Seoul"

# Tortoise는 테스트 DB를 만들 때 DB 이름 없이 먼저 접속하는데, 이때 asyncpg는 사용자 이름과 같은 DB로 접속합니다.
# DB_USER가 postgres가 아니면 그런 DB가 없으므로, 항상 존재하는 postgres DB로 접속하게 합니다.
os.environ.setdefault("PGDATABASE", "postgres")


def get_test_db_config() -> dict[str, Any]:
    tortoise_config = generate_config(
        db_url=f"postgres://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/test",
        app_modules={TEST_DB_LABEL: TORTOISE_APP_MODELS},
        connection_label=TEST_DB_LABEL,
        testing=True,
    )
    tortoise_config["timezone"] = TEST_DB_TZ

    return tortoise_config


_generate_schemas = Tortoise.generate_schemas


async def generate_schemas_with_vector(*args: Any, **kwargs: Any) -> None:
    """테스트 DB에 표를 만들기 전에 pgvector 확장을 켭니다.

    rag_chunks.embedding이 vector 타입이라 확장이 없으면 표를 만들 수 없어요.
    실제 DB는 init 마이그레이션이 확장을 켜지만, 테스트 DB는 마이그레이션 없이 모델로 바로 표를 만듭니다.
    """
    await connections.get(TEST_DB_LABEL).execute_script("CREATE EXTENSION IF NOT EXISTS vector;")
    await _generate_schemas(*args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def initialize(request: FixtureRequest) -> Generator[None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with (
        patch("tortoise.contrib.test.getDBConfig", Mock(return_value=get_test_db_config())),
        patch.object(Tortoise, "generate_schemas", generate_schemas_with_vector),
    ):
        initializer(modules=TORTOISE_APP_MODELS)
    yield
    finalizer()
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")  # type: ignore[type-var]
def event_loop() -> None:
    pass
