from app.models.users import User


class UserRepository:
    def __init__(self):
        self._model = User

    async def get_user(self, user_id: int) -> User | None:
        return await self._model.get_or_none(id=user_id)
