from tortoise import fields, models

from app.models.enums import ConsentType, Gender, SignupType, UserStatus

__all__ = ["Gender", "RefreshToken", "User", "UserConsent"]


class User(models.Model):
    """회원 (ERD v2 users). 카카오 로그인만 제공하므로 비밀번호 컬럼이 없습니다."""

    id = fields.BigIntField(primary_key=True)
    kakao_id = fields.CharField(max_length=100, unique=True, description="카카오 회원번호. 회원 식별 기준")
    email = fields.CharField(max_length=255, null=True, description="카카오에서 동의한 경우에만 저장")
    nickname = fields.CharField(max_length=20, unique=True, description="2~10자. 중복 시 무작위 4자리 부여")
    name = fields.CharField(max_length=50, null=True, description="추가 정보 입력 전까지 NULL")
    birth_date = fields.DateField(null=True, description="추가 정보 입력 전까지 NULL")
    gender = fields.CharEnumField(Gender, max_length=10, null=True, description="추가 정보 입력 전까지 NULL")
    is_profile_completed = fields.BooleanField(default=False, description="추가 정보 입력 완료 여부")
    signup_type = fields.CharEnumField(SignupType, max_length=20, default=SignupType.GENERAL)
    profile_image_url = fields.CharField(max_length=500, null=True, description="[2차]")
    status = fields.CharEnumField(UserStatus, max_length=20, default=UserStatus.ACTIVE)
    kakao_access_token = fields.TextField(null=True, description="[2차] 암호화")
    kakao_access_expires_at = fields.DatetimeField(null=True, description="[2차]")
    kakao_refresh_token = fields.TextField(null=True, description="[2차] 암호화")
    kakao_refresh_expires_at = fields.DatetimeField(null=True, description="[2차]")
    withdrawn_at = fields.DatetimeField(null=True, description="탈퇴 시각. 30일 재가입 제한·영구 삭제 기준")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class UserConsent(models.Model):
    """약관·정보 동의 (ERD v2 user_consents). 동의 철회 시 agreed=False로 갱신합니다."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="consents", on_delete=fields.CASCADE
    )
    consent_type = fields.CharEnumField(ConsentType, max_length=30)
    agreed = fields.BooleanField()
    agreed_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_consents"
        unique_together = (("user", "consent_type"),)


class RefreshToken(models.Model):
    """리프레시 토큰 (ERD v2 refresh_tokens). 원문은 쿠키로만 주고, DB에는 SHA-256 해시만 저장합니다(명세 4-1)."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="refresh_tokens", on_delete=fields.CASCADE
    )
    token_hash = fields.CharField(max_length=255, unique=True, description="SHA-256 hex")
    expires_at = fields.DatetimeField(description="발급 + 14일")
    revoked_at = fields.DatetimeField(null=True, description="로그아웃·재발급(회전)·탈퇴 시 무효화")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "refresh_tokens"
