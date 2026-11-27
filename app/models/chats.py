from tortoise import fields, models
from tortoise.indexes import Index

from app.models.enums import ChatMessageStatus, ChatMessageType, ChatRole, ChatVerifyStatus


class ChatSession(models.Model):
    """챗봇 대화방 (ERD chat_sessions, CHAT-001·003)."""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation = fields.ForeignKeyField(
        "models.User", related_name="chat_sessions", on_delete=fields.CASCADE
    )
    title = fields.CharField(max_length=20, null=True, description="[2차] 첫 질문 앞 20자")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True, description="최근 대화 순 정렬")
    deleted_at = fields.DatetimeField(null=True, description="[2차]")

    messages: fields.ReverseRelation["ChatMessage"]

    class Meta:
        table = "chat_sessions"


class ChatMessage(models.Model):
    """챗봇 메시지 (ERD chat_messages, CHAT-001~006). LLM 요청엔 최근 10턴만."""

    id = fields.BigIntField(primary_key=True)
    session: fields.ForeignKeyRelation[ChatSession] = fields.ForeignKeyField(
        "models.ChatSession", related_name="messages", on_delete=fields.CASCADE
    )
    role = fields.CharEnumField(ChatRole, max_length=20)
    message_type = fields.CharEnumField(ChatMessageType, max_length=30, default=ChatMessageType.NORMAL)
    status = fields.CharEnumField(ChatMessageStatus, max_length=20, default=ChatMessageStatus.COMPLETED)
    content = fields.TextField(description="최대 500자(질문). 암호화")
    is_recommended_question = fields.BooleanField(default=False, description="추천 질문 버튼")
    counts_toward_quota = fields.BooleanField(default=True, description="[2차] 응급·범위 밖·실패는 false")
    check_result = fields.JSONField(null=True, description="check_full() 반환값. 회원 질문 행은 NULL")
    verify_status = fields.CharEnumField(
        ChatVerifyStatus, max_length=20, default=ChatVerifyStatus.NOT_NEEDED, description="[2차] VERI-007"
    )
    correction_note = fields.TextField(null=True)
    prompt_version: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.PromptVersion", related_name="chat_messages", null=True, on_delete=fields.SET_NULL
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
        # Index는 필드 이름이 아니라 컬럼 이름을 받으므로 외래키는 session_id로 적습니다.
        indexes = (Index(fields=("session_id", "created_at")),)
