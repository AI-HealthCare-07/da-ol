from datetime import date, time

from tortoise.contrib.test import TestCase

from app.models.enums import DayType, ParsedBy, PrescriptionSource, TimeBasis
from app.models.prescriptions import DoseCondition, DoseSchedule, Prescription, PrescriptionItem
from app.models.users import User


class TestLocalTimeField(TestCase):
    async def test_time_round_trip_without_timezone(self):
        user = await User.create(kakao_id="kakao-time-test", nickname="시각테스터")
        prescription = await Prescription.create(user=user, source=PrescriptionSource.MANUAL)
        item = await PrescriptionItem.create(
            prescription=prescription,
            drug_name_raw="테스트정",
            dose_text="1정",
            start_date=date(2026, 11, 24),
            total_days=7,
        )
        condition = await DoseCondition.create(
            prescription_item=item, slot_no=1, time_basis=TimeBasis.PRESCRIPTION, parsed_by=ParsedBy.RULE
        )
        schedule = await DoseSchedule.create(
            dose_condition=condition, day_type=DayType.WEEKDAY, calculated_time=time(8, 30)
        )

        loaded = await DoseSchedule.get(id=schedule.id)

        assert loaded.calculated_time == time(8, 30)
        # TIMETZ가 아니라 TIME이므로 시간대 없이 그대로 돌아와야 합니다.
        assert loaded.calculated_time.tzinfo is None
