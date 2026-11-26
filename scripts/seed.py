"""공용 테스트 처방 시나리오(13건) 로컬/개발 DB 적재 스크립트.

- ENV=prod 환경에서는 실행을 즉시 차단합니다.
- 실제 공공데이터(`drugs`)에 매칭되는 약이 있으면 그 행을 연결하고,
  없을 때 경구약은 `drug=None`으로 두며 비경구 거절 테스트(`case13`)용 2종(`SEED_*`)만 생성합니다.
- 테스트용 가짜 약 정리 SQL: `DELETE FROM drugs WHERE item_seq LIKE 'SEED_%';`
"""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from tortoise import Tortoise

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core import config
from app.core.config import Env
from app.core.db.databases import TORTOISE_ORM
from app.dtos.scan import (
    Cycle,
    DocType,
    Dosage,
    DosePerTimeField,
    DrugMatch,
    FieldValue,
    MatchStatus,
    ScanDrug,
    ScanOcrDoneResponse,
    ScanPage,
)
from app.dtos.scan import CycleType as ScanCycleType
from app.dtos.scan import DocumentStatus as ScanDocumentStatus
from app.dtos.scan import ParsedBy as ScanParsedBy
from app.models.documents import MedicalDocument
from app.models.drugs import Drug
from app.models.enums import (
    CycleType,
    DayType,
    DocumentStatus,
    DocumentType,
    DoseConditionType,
    DrugDataSource,
    Gender,
    IntakeStatus,
    MealType,
    ParsedBy,
    PrescriptionSource,
    PrescriptionStatus,
    ScheduleStatus,
    SignupType,
    TimeBasis,
    UserStatus,
)
from app.models.garden import DailyFlower
from app.models.intake import IntakeLog
from app.models.prescriptions import (
    DoseCondition,
    DoseSchedule,
    Prescription,
    PrescriptionItem,
)
from app.models.users import User
from app.services.text_rules import normalize_drug_name

SEED_DATA_PATH = Path(__file__).resolve().parent / "seed_data.json"

# 기본 식사·취침 시각 기준 (추후 recalculate_schedule() 머지 시 해당 함수로 교체)
DEFAULT_MEAL_TIMES: dict[str, time] = {
    "breakfast": time(8, 0),
    "lunch": time(12, 30),
    "dinner": time(18, 30),
    "bedtime": time(23, 0),
}


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _parse_time(value: str | None) -> time | None:
    if value is None:
        return None
    return time.fromisoformat(value)


async def _resolve_drug(item: dict[str, Any]) -> Drug | None:
    """실제 drugs 테이블에서 정규화 이름으로 먼저 찾고, 없을 때는 비경구약 테스트용만 생성한다."""
    drug_name: str = item["drug_name_raw"]
    norm_name = normalize_drug_name(drug_name) or drug_name

    # 1) 실제 적재된 공공데이터(SEED_ 제외) 우선 매칭
    real_drug = await Drug.filter(item_name_norm=norm_name).exclude(item_seq__startswith="SEED_").first()
    if real_drug is not None:
        return real_drug

    # 2) 먹는 약은 공용 drugs 테이블을 오염시키지 않도록 None으로 둠
    if item.get("is_oral", True):
        return None

    # 3) Case 13 비경구약 거절 테스트에 필요한 최소 데이터만 생성
    item_seq: str | None = item.get("item_seq")
    if not item_seq:
        return None

    existing_seed = await Drug.get_or_none(item_seq=item_seq)
    if existing_seed is not None:
        return existing_seed

    return await Drug.create(
        item_seq=item_seq,
        item_name=drug_name,
        item_name_norm=norm_name,
        is_oral=False,
        data_fetched_at=date(2026, 11, 24),
        data_source=DrugDataSource.PERMIT,
        is_otc=False,
    )


def _build_ocr_done_parsed_result(
    doc_id: int,
    doc_type: DocumentType,
    delete_due_at: datetime,
    case: dict[str, Any],
    prescribed_date: date,
    resolved_drugs: list[Drug | None],
) -> str:
    """GET /scans/{scan_id} (명세서 6-2 ScanOcrDoneResponse) 형식으로 parsed_result 생성."""
    scan_drugs: list[ScanDrug] = []
    for idx, (item, drug) in enumerate(zip(case["items"], resolved_drugs, strict=True), start=1):
        dose_amount_raw = item.get("dose_amount")
        parsed_amount = float(dose_amount_raw) if dose_amount_raw is not None else None
        is_dose_parsed = parsed_amount is not None

        scan_drugs.append(
            ScanDrug(
                line_no=idx,
                page_no=1,
                raw_text=item.get("source_text"),
                drug_name=FieldValue[str](
                    value=item["drug_name_raw"],
                    confidence=0.99,
                    needs_check=False,
                ),
                match=DrugMatch(
                    status=MatchStatus.EXACT if drug is not None else MatchStatus.NONE,
                    drug_id=drug.id if drug is not None else None,
                    candidates=[],
                ),
                is_oral=item.get("is_oral"),
                dose_per_time=DosePerTimeField(
                    text=item["dose_text"],
                    min=parsed_amount,
                    max=parsed_amount,
                    unit=item.get("dose_unit") if is_dose_parsed else None,
                    parsed=is_dose_parsed,
                    confidence=0.99 if is_dose_parsed else 0.95,
                    needs_check=not is_dose_parsed,
                    edited=False,
                ),
                times_per_day=FieldValue[int | None](
                    value=item.get("times_per_day"),
                    confidence=0.99,
                    needs_check=False,
                ),
                total_days=FieldValue[int | None](
                    value=item.get("total_days"),
                    confidence=0.99,
                    needs_check=False,
                ),
                instruction_text=item.get("instruction_text"),
                dosage=Dosage(
                    parsed_by=ScanParsedBy.RULE,
                    needs_confirm=False,
                    as_needed=False,
                    doses=[],
                    cycle=Cycle(type=ScanCycleType.DAILY, start_date=prescribed_date),
                ),
            )
        )

    response = ScanOcrDoneResponse(
        scan_id=doc_id,
        status=ScanDocumentStatus.OCR_DONE,
        doc_type=DocType(doc_type.value),
        image_delete_due_at=delete_due_at,
        pages=[ScanPage(page_no=1)],
        masked=False,
        prompt_version="parse_document_v1",
        edited=False,
        hospital_name=FieldValue[str | None](
            value=case.get("hospital_name"),
            confidence=0.99,
            needs_check=False,
        ),
        prescribed_date=FieldValue[date | None](
            value=prescribed_date,
            confidence=0.99,
            needs_check=False,
        ),
        drugs=scan_drugs,
    )
    return response.model_dump_json()


async def run_seed() -> None:
    if config.ENV == Env.PROD:
        raise RuntimeError("운영 환경(ENV=prod)에서는 시드 스크립트를 실행할 수 없습니다.")

    payload: dict[str, Any] = json.loads(SEED_DATA_PATH.read_text(encoding="utf-8"))
    user_data: dict[str, Any] = payload["user"]
    cases: list[dict[str, Any]] = payload["cases"]

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        user, _ = await User.get_or_create(
            kakao_id=user_data["kakao_id"],
            defaults={
                "email": user_data.get("email"),
                "nickname": user_data["nickname"],
                "name": user_data.get("name"),
                "birth_date": _parse_date(user_data.get("birth_date")),
                "gender": Gender(user_data["gender"]) if user_data.get("gender") else None,
                "is_profile_completed": user_data.get("is_profile_completed", True),
                "signup_type": SignupType(user_data.get("signup_type", "general")),
                "status": UserStatus(user_data.get("status", "active")),
            },
        )

        # 재실행 시 중복 생성을 막기 위해 기존 시드 회원의 처방·문서·복약·화단 기록 정리
        await IntakeLog.filter(user=user).delete()
        await DailyFlower.filter(user=user).delete()
        await Prescription.filter(user=user).delete()
        await MedicalDocument.filter(user=user).delete()

        now_utc = datetime.now(UTC)
        today = date.today()
        created_prescriptions = 0
        created_items = 0
        created_conditions = 0
        created_schedules = 0

        for case in cases:
            doc_type = DocumentType(case["doc_type"])
            prescribed_date = _parse_date(case.get("prescribed_date")) or today
            is_confirmed = case["seed_action"] == "confirmed_prescription"

            # 비경구약 거절 테스트용 ocr_done 문서는 만료 정리(run_cleanup)에 걸리지 않도록 365일 부여
            delete_due_at = now_utc + timedelta(hours=3) if is_confirmed else now_utc + timedelta(days=365)

            doc = await MedicalDocument.create(
                user=user,
                doc_type=doc_type,
                status=DocumentStatus.CONFIRMED if is_confirmed else DocumentStatus.OCR_DONE,
                hospital_name=case.get("hospital_name"),
                issued_date=prescribed_date,
                parsed_result=None,
                image_delete_due_at=delete_due_at,
                confirmed_at=now_utc if is_confirmed else None,
            )

            # 비경구약(is_oral=false) 테스트 케이스는 6-2 ScanOcrDoneResponse 모양으로 parsed_result 저장
            if not is_confirmed:
                resolved_drugs = [await _resolve_drug(item) for item in case["items"]]
                doc.parsed_result = _build_ocr_done_parsed_result(
                    doc_id=doc.id,
                    doc_type=doc_type,
                    delete_due_at=delete_due_at,
                    case=case,
                    prescribed_date=prescribed_date,
                    resolved_drugs=resolved_drugs,
                )
                await doc.save(update_fields=["parsed_result"])
                continue

            doc.parsed_result = json.dumps(case, ensure_ascii=False)
            await doc.save(update_fields=["parsed_result"])

            prescription = await Prescription.create(
                user=user,
                document=doc,
                source=PrescriptionSource.OCR,
                hospital_name=case.get("hospital_name"),
                prescribed_date=prescribed_date,
                status=PrescriptionStatus.ACTIVE,
                memo=f"테스트 시나리오 Case {case['case_no']:02d}",
            )
            created_prescriptions += 1

            for item in case["items"]:
                drug = await _resolve_drug(item)
                dose_amount_raw = item.get("dose_amount")
                dose_amount = Decimal(str(dose_amount_raw)) if dose_amount_raw is not None else None

                p_item = await PrescriptionItem.create(
                    prescription=prescription,
                    drug=drug,
                    drug_name_raw=item["drug_name_raw"],
                    source_text=item.get("source_text"),
                    dose_text=item["dose_text"],
                    dose_amount=dose_amount,
                    dose_unit=item.get("dose_unit"),
                    cycle_type=CycleType.DAILY,
                    times_per_day=item.get("times_per_day"),
                    start_date=prescribed_date,
                    total_days=item["total_days"],
                    notify_enabled=True,
                )
                created_items += 1

                for cond in item["conditions"]:
                    cond_type_raw = cond.get("condition_type")
                    meal_raw = cond.get("meal")
                    time_basis = TimeBasis(cond["time_basis"])
                    is_as_needed = cond_type_raw == "as_needed"

                    condition = await DoseCondition.create(
                        prescription_item=p_item,
                        slot_no=cond["slot_no"],
                        condition_type=DoseConditionType(cond_type_raw) if cond_type_raw else None,
                        meal=MealType(meal_raw) if meal_raw else None,
                        offset_minutes=cond.get("offset_minutes"),
                        time_basis=time_basis,
                        source_phrase=item.get("instruction_text"),
                        parsed_by=ParsedBy.RULE,
                        user_confirmed=time_basis != TimeBasis.NEEDS_CHECK,
                    )
                    created_conditions += 1

                    # 필요시(PRN) 약물은 고정 시간표(DoseSchedule)를 만들지 않음
                    if is_as_needed:
                        continue

                    calc_time = _parse_time(cond.get("calculated_time"))
                    sched_status = ScheduleStatus(cond["status"])

                    await DoseSchedule.create(
                        dose_condition=condition,
                        day_type=DayType.WEEKDAY,
                        calculated_time=calc_time,
                        status=sched_status,
                    )
                    created_schedules += 1

                    # 홈 화면·복용 체크 API 테스트용: 오늘 날짜 기준 확약된 일정의 IntakeLog 생성
                    if sched_status == ScheduleStatus.OK and calc_time is not None:
                        is_morning_taken = case["case_no"] == 1 and cond["slot_no"] == 1
                        await IntakeLog.create(
                            user=user,
                            prescription_item=p_item,
                            dose_condition=condition,
                            log_date=today,
                            scheduled_time=calc_time,
                            dose_text=item["dose_text"],
                            is_as_needed=False,
                            status=IntakeStatus.TAKEN if is_morning_taken else IntakeStatus.PENDING,
                            taken_at=now_utc if is_morning_taken else None,
                        )

        # 어제 날짜 화단 꽃 피우기 테스트 데이터 1건 생성
        await DailyFlower.create(
            user=user,
            log_date=today - timedelta(days=1),
            flower_type_id=None,
            is_rest_day=False,
            points_awarded=0,
        )

        print(
            "Seed completed: "
            f"user={user.nickname}(id={user.id}), "
            f"prescriptions={created_prescriptions}, "
            f"items={created_items}, "
            f"conditions={created_conditions}, "
            f"schedules={created_schedules}"
        )
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(run_seed())
