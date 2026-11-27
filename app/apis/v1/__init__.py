from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.chat_routers import chat_router
from app.apis.v1.drug_routers import drug_router
from app.apis.v1.guide_routers import guide_router
from app.apis.v1.home_routers import home_router
from app.apis.v1.intake_routers import intake_router
from app.apis.v1.prescription_routers import prescription_router
from app.apis.v1.scan_routers import scan_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")

# 명세 3장 순서: 인증·회원(4장) → 복용 기록 → 홈·처방(5장) → 처방 등록·약 검색(6장) → 가이드·챗봇(7장)
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(intake_router)
v1_routers.include_router(home_router)
v1_routers.include_router(prescription_router)
v1_routers.include_router(scan_router)
v1_routers.include_router(drug_router)
v1_routers.include_router(guide_router)
v1_routers.include_router(chat_router)
