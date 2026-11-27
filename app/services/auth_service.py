"""카카오 로그인 · 토큰 재발급 · 로그아웃 (명세 4-1).

- 액세스 토큰: JWT(30분). 응답 본문으로만 줍니다.
- 리프레시 토큰: 무작위 문자열(14일). 쿠키로만 주고 DB에는 SHA-256 해시만 저장합니다.
  재발급 때마다 새것으로 바꾸고(회전), 이미 쓴 토큰이 다시 오면 탈취로 보고 그 회원의 토큰을 모두 무효화합니다.
"""

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from starlette import status
from tortoise import timezone
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.core import config
from app.core.exceptions import AppError, ErrorCode
from app.models.enums import UserStatus
from app.models.users import RefreshToken, User
from app.services.jwt import JwtService
from app.services.kakao_oauth import KakaoOAuthClient

REFRESH_TOKEN_LIFETIME = timedelta(minutes=config.REFRESH_TOKEN_EXPIRE_MINUTES)
REJOIN_RESTRICTION = timedelta(days=30)

NICKNAME_MIN = 2
NICKNAME_MAX = 10
NICKNAME_SUFFIX_LEN = 4
NICKNAME_SUFFIX_CHARS = string.ascii_lowercase + string.digits
NICKNAME_PREFIX_WHEN_TOO_LONG = NICKNAME_MAX - NICKNAME_SUFFIX_LEN  # 6자
DEFAULT_NICKNAME = "다올이"  # 카카오 닉네임을 못 받았을 때
NICKNAME_MAX_TRIES = 10


def refresh_token_expired() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.REFRESH_TOKEN_EXPIRED, "로그인이 만료되었습니다")


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def random_suffix() -> str:
    return "".join(secrets.choice(NICKNAME_SUFFIX_CHARS) for _ in range(NICKNAME_SUFFIX_LEN))


def nickname_with_suffix(base: str, suffix: str) -> str:
    """명세 4-1: 뒤에 무작위 4자리를 붙이고, 10자를 넘으면 앞부분을 6자로 자른 뒤 붙입니다."""
    if len(base) + len(suffix) > NICKNAME_MAX:
        base = base[:NICKNAME_PREFIX_WHEN_TOO_LONG]
    return base + suffix


def nickname_base(kakao_nickname: str | None) -> str:
    base = (kakao_nickname or "").strip() or DEFAULT_NICKNAME
    return base[:NICKNAME_MAX]


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class LoginResult:
    user: User
    is_new_user: bool
    tokens: IssuedTokens


class AuthService:
    def __init__(self, kakao_client: KakaoOAuthClient | None = None, jwt_service: JwtService | None = None) -> None:
        self._kakao = kakao_client or KakaoOAuthClient()
        self._jwt = jwt_service or JwtService()

    # ---- 카카오 로그인 ----
    async def kakao_login(self, code: str) -> LoginResult:
        kakao_user = await self._kakao.fetch_user(code)

        user = await User.get_or_none(kakao_id=kakao_user.kakao_id)
        is_new_user = False
        if user is not None and user.status == UserStatus.WITHDRAWN:
            self._check_rejoin_allowed(user)
            # 30일이 지났는데 아직 영구 삭제 전인 행: 명세상 30일 뒤에는 새 회원으로 가입하므로 지우고 새로 만듭니다.
            # 삭제와 생성을 한 트랜잭션으로 묶어, 생성이 실패하면 옛 행도 그대로 남게 합니다.
            async with in_transaction():
                await user.delete()
                user = await self._create_user(kakao_user.kakao_id, kakao_user.nickname, kakao_user.email)
            is_new_user = True
        elif user is None:
            user = await self._create_user(kakao_user.kakao_id, kakao_user.nickname, kakao_user.email)
            is_new_user = True

        tokens = await self.issue_tokens(user)
        return LoginResult(user=user, is_new_user=is_new_user, tokens=tokens)

    @staticmethod
    def _check_rejoin_allowed(user: User) -> None:
        if user.withdrawn_at is None:
            return
        available_at = timezone.localtime(user.withdrawn_at + REJOIN_RESTRICTION, str(config.TIMEZONE))
        if timezone.now() < available_at:
            available_date = available_at.date()
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                ErrorCode.REJOIN_RESTRICTED,
                f"탈퇴 후 30일 동안은 다시 가입할 수 없어요. {available_date.month}월 {available_date.day}일부터 가입할 수 있어요",
                extra={"rejoin_available_date": available_date.isoformat()},
            )

    @staticmethod
    async def _create_user(kakao_id: str, kakao_nickname: str | None, email: str | None) -> User:
        base = nickname_base(kakao_nickname)
        # 1자면 처음부터 4자리를 붙여 2자 이상으로 만듭니다.
        candidate = base if len(base) >= NICKNAME_MIN else nickname_with_suffix(base, random_suffix())

        for _ in range(NICKNAME_MAX_TRIES):
            if not await User.filter(nickname=candidate).exists():
                try:
                    async with in_transaction():
                        return await User.create(kakao_id=kakao_id, nickname=candidate, email=email)
                except IntegrityError:
                    # 동시에 같은 닉네임(또는 같은 카카오 계정)이 들어온 경우
                    existing = await User.get_or_none(kakao_id=kakao_id)
                    if existing is not None:
                        return existing
            candidate = nickname_with_suffix(base, random_suffix())

        raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, "잠시 후 다시 시도해 주세요")

    # ---- 토큰 ----
    async def issue_tokens(self, user: User) -> IssuedTokens:
        raw = secrets.token_urlsafe(48)
        await RefreshToken.create(
            user=user,
            token_hash=hash_refresh_token(raw),
            expires_at=timezone.now() + REFRESH_TOKEN_LIFETIME,
        )
        access_token = str(self._jwt.create_access_token(user))
        return IssuedTokens(access_token=access_token, refresh_token=raw)

    async def refresh(self, raw: str | None) -> IssuedTokens:
        if not raw:
            raise refresh_token_expired()

        token = await RefreshToken.get_or_none(token_hash=hash_refresh_token(raw)).select_related("user")
        if token is None:
            raise refresh_token_expired()

        now = timezone.now()
        if token.revoked_at is not None:
            await self._revoke_all(token.user_id, now)  # type: ignore[attr-defined]
            raise refresh_token_expired()
        if token.expires_at <= now or token.user.status == UserStatus.WITHDRAWN:
            raise refresh_token_expired()

        # 동시에 같은 토큰으로 두 번 들어오면 한쪽만 성공합니다(조건부 갱신).
        updated = await RefreshToken.filter(id=token.id, revoked_at__isnull=True).update(revoked_at=now)
        if updated == 0:
            await self._revoke_all(token.user_id, now)  # type: ignore[attr-defined]
            raise refresh_token_expired()

        return await self.issue_tokens(token.user)

    async def logout(self, user: User, raw: str | None) -> None:
        """이 기기의 토큰만 무효화합니다. 쿠키가 없거나 이미 무효화돼도 조용히 끝냅니다."""
        if not raw:
            return
        await RefreshToken.filter(token_hash=hash_refresh_token(raw), user_id=user.id, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )

    @staticmethod
    async def _revoke_all(user_id: int, now: datetime) -> None:
        await RefreshToken.filter(user_id=user_id, revoked_at__isnull=True).update(revoked_at=now)
