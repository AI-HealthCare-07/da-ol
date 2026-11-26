from tortoise import fields, models

from app.models.enums import Gender, SignupType, UserStatus

__all__ = ["Gender", "User"]


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
