"""pgvector 필드(rag_chunks.embedding): 저장·읽기와 코사인 거리 검색이 되는지 확인합니다."""

from tortoise import connections
from tortoise.contrib.test import TestCase

from app.models.enums import RagSourceType
from app.models.rag import RagChunk, RagDocument


def one_hot(index: int) -> list[float]:
    """index 자리만 1이고 나머지는 0인 1536차원 벡터 (테스트용 가짜 임베딩)."""
    vector = [0.0] * 1536
    vector[index] = 1.0
    return vector


class TestVectorField(TestCase):
    async def test_embedding_round_trip(self):
        document = await RagDocument.create(source_type=RagSourceType.GUIDELINE, title="가상 생활습관 자료")
        chunk = await RagChunk.create(rag_document=document, chunk_no=1, content="가상 조각", embedding=one_hot(0))

        loaded = await RagChunk.get(id=chunk.id)

        assert len(loaded.embedding) == 1536
        assert loaded.embedding[0] == 1.0
        assert loaded.embedding_model == "text-embedding-3-small"

    async def test_nearest_chunk_by_cosine_distance(self):
        document = await RagDocument.create(source_type=RagSourceType.GUIDELINE, title="가상 생활습관 자료")
        await RagChunk.create(rag_document=document, chunk_no=1, content="첫째 조각", embedding=one_hot(0))
        await RagChunk.create(rag_document=document, chunk_no=2, content="둘째 조각", embedding=one_hot(1))

        question = RagChunk._meta.fields_map["embedding"].to_db_value(one_hot(1), RagChunk)
        rows = await connections.get("models").execute_query_dict(
            'SELECT content FROM "rag_chunks" ORDER BY embedding <=> $1::vector LIMIT 1', [question]
        )

        assert rows[0]["content"] == "둘째 조각"
