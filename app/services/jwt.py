from app.core.jwt.tokens import AccessToken
from app.models.users import User


class JwtService:
    """액세스 토큰(JWT) 발급. 검증은 `app.dependencies.security.get_request_user`가 합니다.

    리프레시 토큰은 JWT가 아니라 무작위 문자열이라 `app.services.auth_service`가 만듭니다(명세 4-1).
    """

    access_token_class = AccessToken

    def create_access_token(self, user: User) -> AccessToken:
        return self.access_token_class.for_user(user)
