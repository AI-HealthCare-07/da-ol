from typing import Literal

from pydantic import BaseModel, Field


class KakaoLoginRequest(BaseModel):
    code: str = Field(min_length=1, description="카카오가 redirect_uri로 넘겨준 인가 코드")


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="액세스 토큰 유효 시간(초)")


class LoginUser(BaseModel):
    user_id: int
    nickname: str


class KakaoLoginResponse(AccessTokenResponse):
    is_new_user: bool
    is_profile_completed: bool
    user: LoginUser


class TokenRefreshResponse(AccessTokenResponse): ...
