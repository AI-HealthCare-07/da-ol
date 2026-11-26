"""drugs 줄 파일(JSON Lines)을 DB drugs 테이블에 넣기.

- build_drug_rows.py로 만든 data/processed/drugs_rows_<날짜>.jsonl을 읽습니다.
- item_name_norm은 normalize_drug_name()(app/services/text_rules.py)으로 채웁니다.
- 같은 품목기준코드(item_seq)가 이미 있으면 새 값으로 덮어씁니다. 그래서 다시 실행해도 됩니다.
- 레포 맨 위 .env의 DB 설정을 씁니다. docker의 db가 켜져 있어야 합니다.

실행 (레포 맨 위에서): uv run python -m scripts.drugs.load_drugs
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from tortoise import Tortoise

from app.core.db.databases import TORTOISE_ORM
from app.models.drugs import Drug
from app.models.enums import DrugDataSource
from app.services.text_rules import normalize_drug_name

FETCHED = "20261124"  # build_drug_rows.py와 같은 날짜
ROWS_FILE = Path.home() / "Documents" / "final_project" / "data" / "processed" / f"drugs_rows_{FETCHED}.jsonl"
BATCH_SIZE = 500  # 한 번에 넣는 줄 수
UPDATE_FIELDS = [
    "item_name",
    "item_name_norm",
    "ingredient_name",
    "company",
    "efficacy",
    "usage_text",
    "precautions",
    "side_effects",
    "storage_method",
    "is_oral",
    "image_url",
    "data_fetched_at",
    "data_source",
    "source_updated_at",
    "is_otc",
]


def to_drug(row: dict) -> Drug:
    """줄 하나(dict)를 Drug 모델로 바꿉니다. 날짜 글자는 날짜로, 출처는 정해진 값으로."""
    return Drug(
        **{
            **row,
            "item_name_norm": normalize_drug_name(row["item_name"]),
            "data_source": DrugDataSource(row["data_source"]),
            "data_fetched_at": date.fromisoformat(row["data_fetched_at"]),
            "source_updated_at": date.fromisoformat(row["source_updated_at"]) if row["source_updated_at"] else None,
        }
    )


async def save_batch(batch: list[Drug]) -> None:
    await Drug.bulk_create(batch, on_conflict=["item_seq"], update_fields=UPDATE_FIELDS)


async def load(rows_file: Path) -> int:
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        before = await Drug.all().count()
        batch: list[Drug] = []
        done = 0
        with rows_file.open(encoding="utf-8") as f:
            for line in f:
                batch.append(to_drug(json.loads(line)))
                if len(batch) == BATCH_SIZE:
                    await save_batch(batch)
                    done += len(batch)
                    batch = []
                    if done % 5000 == 0:
                        print(f"{done}줄 넣음")
        if batch:
            await save_batch(batch)
            done += len(batch)
        after = await Drug.all().count()
        print(f"완료: 파일 {done}줄 / DB drugs {before}개 → {after}개")
        return 0 if after >= done else 1
    finally:
        await Tortoise.close_connections()


def main() -> int:
    rows_file = Path(sys.argv[1]) if len(sys.argv) > 1 else ROWS_FILE
    if not rows_file.exists():
        print(f"파일이 없어요: {rows_file}")
        return 1
    return asyncio.run(load(rows_file))


if __name__ == "__main__":
    sys.exit(main())
