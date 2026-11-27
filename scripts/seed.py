"""공용 테스트 처방 시나리오(13건) 로컬/개발 DB 적재 스크립트.

- ENV=prod 환경에서는 실행을 즉시 차단합니다.
- 한국 시간(KST, Asia/Seoul) 기준으로 최근 7일(지난 6일 + 오늘) 복약 기록과 꽃 데이터를 생성합니다.
- 실제 공공데이터(`drugs`)에 매칭되는 약이 있으면 그 행을 연결하고,
  없을 때 경구약은 `drug=None`으로 두며 비경구 거절 테스트(`case13`)용 2종(`SEED_*`)만 생성합니다.
- 테스트용 가짜 약 정리 SQL: `DELETE FROM drugs WHERE item_seq LIKE 'SEED_%';`
"""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, time, timedelta
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
    DosePerTime,
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
    ConsentType,
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
from app.models.users import User, UserConsent
from app.services.text_rules import normalize_drug_name, parse_dose_text

SEED_DATA_PATH = Path(__file__).resolve().parent / "seed_data.json"

REQUIRED_CONSENTS: tuple[ConsentType, ...] = (
    ConsentType.TERMS,
    ConsentType.PRIVACY,
    ConsentType.SENSITIVE_HEALTH,
)

# 최근 7일(오늘 기준 며칠 전인지) 중 모든 복약을 완료해 꽃을 피우는 날짜 오프셋
FULL_TAKEN_OFFSETS: set[int] = {6, 4, 3, 1}


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def _parse_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value is not None else None


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
    """GET /scans/{scan_id} 조립에 필요한 parsed_result 6개 핵심 필드만 직렬화한다."""
    scan_drugs: list[ScanDrug] = []
    for idx, (item, drug) in enumerate(zip(case["items"], resolved_drugs, strict=True), start=1):
        parsed_dose = DosePerTime.model_validate(parse_dose_text(item["dose_text"]))

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
                    text=parsed_dose.text,
                    min=parsed_dose.min,
                    max=parsed_dose.max,
                    unit=parsed_dose.unit,
                    parsed=parsed_dose.parsed,
                    confidence=0.99 if parsed_dose.parsed else 0.95,
                    needs_check=not parsed_dose.parsed,
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
        masked=True,
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
    return json.dumps(
        response.model_dump(
            mode="json",
            include={
                "masked",
                "prompt_version",
                "edited",
                "hospital_name",
                "prescribed_date",
                "drugs",
            },
        ),
        ensure_ascii=False,
    )


async def _reset_user_and_consents(user: User) -> None:
    """재실행 시 중복 생성을 막기 위해 기존 시드 데이터를 지우고 약관 동의 3종을 적재한다."""
    await UserConsent.filter(user=user).delete()
    await IntakeLog.filter(user=user).delete()
    await DailyFlower.filter(user=user).delete()
    await Prescription.filter(user=user).delete()
    await MedicalDocument.filter(user=user).delete()

    for consent_type in REQUIRED_CONSENTS:
        await UserConsent.create(
            user=user,
            consent_type=consent_type,
            agreed=True,
        )


def _determine_intake_status(
    day_offset: int,
    case_no: int,
    slot_no: int,
    calc_time: time,
) -> IntakeStatus:
    """날짜 오프셋에 따라 다 먹은 날 / 일부만 먹은 날 / 오늘 상태를 결정한다."""
    if day_offset in FULL_TAKEN_OFFSETS:
        return IntakeStatus.TAKEN
    if day_offset == 0:
        # 오늘 TAKEN은 Case 01의 아침 약(아모잘탄정 08:30) 1건만 생성
        is_today_morning = case_no == 1 and slot_no == 1 and calc_time == time(8, 30)
        return IntakeStatus.TAKEN if is_today_morning else IntakeStatus.PENDING
    return IntakeStatus.TAKEN if slot_no == 1 else IntakeStatus.MISSED


async def _seed_7day_intakes(
    user: User,
    p_item: PrescriptionItem,
    condition: DoseCondition,
    calc_time: time,
    case_no: int,
    slot_no: int,
    dose_text: str,
    end_date: date,
    today_kst: date,
) -> int:
    """KST 기준 최근 7일(지난 6일 + 오늘) 중 복용 기간(end_date) 이내의 복약 기록만 생성한다."""
    created = 0
    for day_offset in range(6, -1, -1):
        target_date = today_kst - timedelta(days=day_offset)
        if target_date > end_date:
            continue

        status = _determine_intake_status(day_offset, case_no, slot_no, calc_time)
        taken_at = (
            datetime.combine(target_date, calc_time, tzinfo=config.TIMEZONE) if status == IntakeStatus.TAKEN else None
        )
        await IntakeLog.create(
            user=user,
            prescription_item=p_item,
            dose_condition=condition,
            log_date=target_date,
            scheduled_time=calc_time,
            dose_text=dose_text,
            is_as_needed=False,
            status=status,
            taken_at=taken_at,
        )
        created += 1
    return created


async def _seed_condition_and_schedules(
    user: User,
    p_item: PrescriptionItem,
    item: dict[str, Any],
    cond: dict[str, Any],
    case_no: int,
    end_date: date,
    today_kst: date,
) -> tuple[int, int]:
    """복용 조건 1건과 평일·주말 시간표, 복용 기간 내 복약 로그를 생성한다."""
    cond_type_raw = cond.get("condition_type")
    meal_raw = cond.get("meal")
    time_basis = TimeBasis(cond["time_basis"])

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

    if cond_type_raw == "as_needed":
        return 0, 0

    calc_time = _parse_time(cond.get("calculated_time"))
    sched_status = ScheduleStatus(cond["status"])

    # 주말에 실행해도 홈이 비지 않도록 평일·주말 일정 모두 생성
    for day_type in (DayType.WEEKDAY, DayType.WEEKEND):
        await DoseSchedule.create(
            dose_condition=condition,
            day_type=day_type,
            calculated_time=calc_time,
            status=sched_status,
        )

    intakes_created = 0
    if sched_status == ScheduleStatus.OK and calc_time is not None:
        intakes_created = await _seed_7day_intakes(
            user=user,
            p_item=p_item,
            condition=condition,
            calc_time=calc_time,
            case_no=case_no,
            slot_no=cond["slot_no"],
            dose_text=item["dose_text"],
            end_date=end_date,
            today_kst=today_kst,
        )
    return 2, intakes_created


async def _seed_confirmed_case(
    user: User,
    doc: MedicalDocument,
    case: dict[str, Any],
    prescribed_date: date,
    today_kst: date,
) -> tuple[int, int, int, int]:
    """확정 처방 1건과 하위 약품·조건·일정·복약 로그를 적재한다."""
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

    items_cnt = 0
    conds_cnt = 0
    scheds_cnt = 0
    intakes_cnt = 0

    for item in case["items"]:
        drug = await _resolve_drug(item)
        dose_amount_raw = item.get("dose_amount")
        dose_amount = Decimal(str(dose_amount_raw)) if dose_amount_raw is not None else None
        total_days: int = item["total_days"]
        end_date = prescribed_date + timedelta(days=total_days - 1)

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
            total_days=total_days,
            notify_enabled=True,
        )
        items_cnt += 1

        for cond in item["conditions"]:
            s_cnt, i_cnt = await _seed_condition_and_schedules(
                user=user,
                p_item=p_item,
                item=item,
                cond=cond,
                case_no=case["case_no"],
                end_date=end_date,
                today_kst=today_kst,
            )
            conds_cnt += 1
            scheds_cnt += s_cnt
            intakes_cnt += i_cnt

    return items_cnt, conds_cnt, scheds_cnt, intakes_cnt


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
        await _reset_user_and_consents(user)

        now_kst = datetime.now(config.TIMEZONE)
        today_kst = now_kst.date()
        week_start_kst = today_kst - timedelta(days=6)

        totals = {"prescriptions": 0, "items": 0, "conditions": 0, "schedules": 0, "intakes": 0}

        for case in cases:
            doc_type = DocumentType(case["doc_type"])
            is_confirmed = case["seed_action"] == "confirmed_prescription"
            prescribed_date = (
                week_start_kst if is_confirmed else (_parse_date(case.get("prescribed_date")) or today_kst)
            )
            # 비경구 테스트 문서는 만료 정리(run_cleanup)에 걸리지 않도록 365일 부여
            delete_due_at = now_kst + timedelta(hours=3) if is_confirmed else now_kst + timedelta(days=365)

            doc = await MedicalDocument.create(
                user=user,
                doc_type=doc_type,
                status=DocumentStatus.CONFIRMED if is_confirmed else DocumentStatus.OCR_DONE,
                hospital_name=case.get("hospital_name"),
                issued_date=prescribed_date,
                parsed_result=None,
                image_delete_due_at=delete_due_at,
                confirmed_at=now_kst if is_confirmed else None,
            )

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

            i_cnt, c_cnt, s_cnt, in_cnt = await _seed_confirmed_case(
                user=user,
                doc=doc,
                case=case,
                prescribed_date=prescribed_date,
                today_kst=today_kst,
            )
            totals["prescriptions"] += 1
            totals["items"] += i_cnt
            totals["conditions"] += c_cnt
            totals["schedules"] += s_cnt
            totals["intakes"] += in_cnt

        # 지난 6일 중 100% 복용 완료한 날짜에만 꽃(DailyFlower) 생성 (일부만 먹은 날은 행 없음 = 빈 흙)
        created_flowers = 0
        for day_offset in sorted(FULL_TAKEN_OFFSETS, reverse=True):
            await DailyFlower.create(
                user=user,
                log_date=today_kst - timedelta(days=day_offset),
                flower_type_id=None,
                is_rest_day=False,
                points_awarded=0,
            )
            created_flowers += 1

        print(
            "Seed completed: "
            f"user={user.nickname}(id={user.id}), "
            f"consents={len(REQUIRED_CONSENTS)}, "
            f"prescriptions={totals['prescriptions']}, "
            f"items={totals['items']}, "
            f"conditions={totals['conditions']}, "
            f"schedules={totals['schedules']}, "
            f"intakes={totals['intakes']}, "
            f"flowers={created_flowers}"
        )
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(run_seed())
