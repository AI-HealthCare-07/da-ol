from tortoise import fields, models

from app.models.enums import RagSourceType
from app.models.fields import VectorField


class RagDocument(models.Model):
    """근거 문서 1건 (ERD rag_documents, GUIDE-003). 조각과 임베딩은 rag_chunks.

    LLM 입력에는 식약처 공공데이터와 공공누리 제1유형 공식 자료만 넣습니다(11/26 결정).
    """

    id = fields.BigIntField(primary_key=True)
    source_type = fields.CharEnumField(RagSourceType, max_length=20, description="1차는 guideline만")
    title = fields.CharField(max_length=300, description="가이드 하단 출처(문서명)")
    publisher = fields.CharField(max_length=100, null=True, description="출처 표시용 기관명")
    published_at = fields.DateField(null=True, description="자료 발표일")
    source_url = fields.CharField(max_length=500, null=True)
    drug: fields.ForeignKeyNullableRelation = fields.ForeignKeyField(
        "models.Drug",
        related_name="rag_documents",
        null=True,
        on_delete=fields.SET_NULL,
        description="source_type=drug_info일 때만 (1차 미사용)",
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    chunks: fields.ReverseRelation["RagChunk"]

    class Meta:
        table = "rag_documents"


class RagChunk(models.Model):
    """문서 조각 + 임베딩 (ERD rag_chunks). 검색은 SQL로 `ORDER BY embedding <=> 질문벡터 LIMIT 5`."""

    id = fields.BigIntField(primary_key=True)
    rag_document: fields.ForeignKeyRelation[RagDocument] = fields.ForeignKeyField(
        "models.RagDocument", related_name="chunks", on_delete=fields.CASCADE
    )
    chunk_no = fields.IntField(description="문서 안 순서(1부터)")
    section = fields.CharField(max_length=200, null=True, description="조각이 속한 제목")
    content = fields.TextField(description="원문 조각 글")
    # HNSW 인덱스(vector_cosine_ops)는 마이그레이션 SQL에 직접 추가
    embedding = VectorField(description="content의 임베딩 (text-embedding-3-small, 1536차원)")
    embedding_model = fields.CharField(max_length=50, default="text-embedding-3-small")
    search_text = fields.TextField(null=True, description="[2차] 키워드 검색(Kiwi+BM25)용 글. 1차는 NULL")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "rag_chunks"
        unique_together = (("rag_document", "chunk_no"),)
