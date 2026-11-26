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

from app.core.db.databases import TORTOISE_ORM  # noqa: E402
from app.models.documents import MedicalDocument  # noqa: E402
from app.models.drugs import Drug  # noqa: E402
from app.models.enums import (  # noqa: E402
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
from app.models.garden import DailyFlower  # noqa: E402
from app.models.intake import IntakeLog  # noqa: E402
from app.models.prescriptions import (  # noqa: E402
    DoseCondition,
    DoseSchedule,
    Prescription,
    PrescriptionItem,
)
from app.models.users import User  # noqa: E402
from app.services.text_rules import normalize_drug_name  # noqa: E402

SEED_DATA_PATH = Path(__file__).resolve().parent / "seed_data.json"


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _parse_time(value: str | None) -> time | None:
    if value is None:
        return None
    return time.fromisoformat(value)


async def _get_or_create_drug(item: dict[str, Any]) -> Drug | None:
    item_seq: str | None = item.get("item_seq")
    if not item_seq:
        return None

    drug_name: str = item["drug_name_raw"]
    norm_name = normalize_drug_name(drug_name) or drug_name

    existing = await Drug.get_or_none(item_seq=item_seq)
    if existing is not None:
        return existing

    by_norm = await Drug.filter(item_name_norm=norm_name).first()
    if by_norm is not None:
        return by_norm

    return await Drug.create(
        item_seq=item_seq,
        item_name=drug_name,
        item_name_norm=norm_name,
        is_oral=item.get("is_oral", True),
        data_fetched_at=date(2026, 11, 24),
        data_source=DrugDataSource.PERMIT,
        is_otc=False,
    )


async def run_seed() -> None:
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

            doc = await MedicalDocument.create(
                user=user,
                doc_type=doc_type,
                status=DocumentStatus.CONFIRMED if is_confirmed else DocumentStatus.OCR_DONE,
                hospital_name=case.get("hospital_name"),
                issued_date=prescribed_date,
                parsed_result=json.dumps(case, ensure_ascii=False),
                image_delete_due_at=now_utc + timedelta(hours=3),
                confirmed_at=now_utc if is_confirmed else None,
            )

            # 비경구약(is_oral=false) 테스트 케이스는 drugs 마스터만 등록하고 처방 확정은 건너뜀
            if not is_confirmed:
                for item in case["items"]:
                    await _get_or_create_drug(item)
                continue

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
                drug = await _get_or_create_drug(item)
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
                        source_phrase=item.get("source_text"),
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
