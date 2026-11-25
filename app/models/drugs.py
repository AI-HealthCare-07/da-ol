from tortoise import fields, models

from app.models.enums import DrugDataSource


class Drug(models.Model):
    """약 마스터 (ERD v2 drugs). e약은요 / 의약품 허가정보에서 사전 적재."""

    id = fields.BigIntField(primary_key=True)
    item_seq = fields.CharField(max_length=20, unique=True, description="식약처 품목기준코드")
    item_name = fields.CharField(max_length=500, db_index=True, description="상품명")
    # 이름 검색용. pg_trgm GIN 인덱스(gin_trgm_ops)는 init-db 때 마이그레이션 SQL에 직접 추가
    item_name_norm = fields.CharField(max_length=500, description="normalize_drug_name()으로 정규화한 이름")
    ingredient_name = fields.CharField(max_length=500, null=True, db_index=True, description="화면 표시용 성분명")
    company = fields.CharField(max_length=100, null=True)
    efficacy = fields.TextField(null=True)
    usage_text = fields.TextField(null=True)
    precautions = fields.TextField(null=True)
    side_effects = fields.TextField(null=True)
    storage_method = fields.TextField(null=True)
    is_oral = fields.BooleanField(null=True, description="먹는 약 여부. 모르면 NULL")
    image_url = fields.CharField(max_length=500, null=True)
    data_fetched_at = fields.DateField(description="데이터를 받아 온 날")
    # easy_drug / permit만 허용. DB CHECK 제약은 init-db 때 마이그레이션 SQL에 직접 추가
    data_source = fields.CharEnumField(DrugDataSource, max_length=20)
    source_updated_at = fields.DateField(null=True, description="식약처 쪽 마지막 수정일")
    is_otc = fields.BooleanField(null=True, description="일반의약품 여부. 모르면 NULL")

    class Meta:
        table = "drugs"
