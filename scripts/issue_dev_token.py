"""개발/로컬 테스트용 시드 회원 액세스 토큰 발급 스크립트.

- 카카오 로그인을 거치지 않고 Swagger(/api/docs)나 API 클라이언트를 테스트할 때 사용합니다.
- ENV=prod 환경에서는 실행을 즉시 차단합니다.
- 사전 조건: `scripts/seed.py`를 먼저 실행해 시드 회원(`seed_kakao_daol_01`)이 생성되어 있어야 합니다.
"""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from tortoise import Tortoise

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core import config
from app.core.config import Env
from app.core.db.databases import TORTOISE_ORM
from app.models.users import User
from app.services.jwt import JwtService

SEED_KAKAO_ID = "seed_kakao_daol_01"


async def issue_dev_token() -> None:
    if config.ENV == Env.PROD:
        raise RuntimeError("운영 환경(ENV=prod)에서는 개발용 토큰 발급 스크립트를 실행할 수 없습니다.")

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        user = await User.get_or_none(kakao_id=SEED_KAKAO_ID)
        if user is None:
            raise RuntimeError(f"시드 회원({SEED_KAKAO_ID})이 없습니다. 먼저 `python scripts/seed.py`를 실행해 주세요.")

        access_token = str(JwtService().create_access_token(user))
        print(f"User: {user.nickname} (id={user.id}, kakao_id={user.kakao_id})")
        print(f"Expires in: {config.ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
        print("\n[Access Token]")
        print(access_token)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(issue_dev_token())
