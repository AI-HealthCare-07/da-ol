"""7장 가이드·챗봇 API의 응답 예시 (가짜 응답 API용).

- API 명세서 7-1 ~ 7-6의 응답 예시를 그대로 옮겼습니다. 약·병원 이름은 모두 가상입니다.
- 실제 구현이 들어오면 라우터는 이 예시 대신 DB·AI 결과를 돌려줍니다. 테스트와 Swagger 예시로는 계속 씁니다.
"""

DISCLAIMER = "본 안내는 참고용이며, 의사·약사의 진료와 복약지도를 대체하지 않습니다."
DRUG_SOURCE = {"drug_id": 1203, "name": "의약품개요정보(e약은요): 가상캡슐"}
GUIDELINE_SOURCE = {
    "rag_document_id": 31,
    "name": "한국인을 위한 식생활지침 (보건복지부·농림축산식품부·식품의약품안전처)",
}

# 7-1 완성
GUIDE_COMPLETED = {
    "prescription_id": 123,
    "is_outdated": False,
    "used_default_profile": False,
    "disclaimer": DISCLAIMER,
    "medication": {
        "guide_id": 9001,
        "status": "completed_with_replacements",
        "created_at": "2026-11-20T09:01:10+09:00",
        "content": {
            "drugs": [
                {
                    "prescription_item_id": 502,
                    "drug_name": "가상캡슐",
                    "has_public_data": True,
                    "how_to_take": {
                        "dose_per_time": {"text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": True},
                        "times_per_day": 2,
                        "total_days": 30,
                        "dose_times": ["08:30", "19:00"],
                        "easy_text": "하루 두 번, 아침과 저녁 식사 후 30분에 1캡슐씩 드세요.",
                    },
                    "cautions": [
                        {"item_id": "d1-c1", "text": "가상 주의 문장이에요.", "sources": [DRUG_SOURCE], "check": None}
                    ],
                    "side_effects": [
                        {
                            "item_id": "d1-s1",
                            "symptom": "가상 부작용이에요.",
                            "what_to_do": "증상이 계속되면 의사·약사에게 알려 주세요",
                            "sources": [DRUG_SOURCE],
                            "check": None,
                        }
                    ],
                    "see_doctor_if": [
                        {
                            "item_id": "d1-h1",
                            "text": "이 부분은 의사·약사에게 확인해 주세요",
                            "sources": [DRUG_SOURCE],
                            "check": "fallback",
                        }
                    ],
                }
            ],
            "sources": [{**DRUG_SOURCE, "data_fetched_at": "2026-11-24"}],
        },
    },
    "lifestyle": {
        "guide_id": 9002,
        "status": "completed",
        "created_at": "2026-11-20T09:01:10+09:00",
        "content": {
            "diet": [
                {"item_id": "l-d1", "text": "가상 식단 문장이에요.", "sources": [GUIDELINE_SOURCE], "check": None}
            ],
            "exercise": [],
            "sleep": [],
            "smoking_alcohol": [],
            "sources": [GUIDELINE_SOURCE],
        },
    },
}

# 7-1 만드는 중 (만드는 중·실패에도 is_outdated·used_default_profile·disclaimer 키를 항상 넣음)
GUIDE_IN_PROGRESS = {
    "prescription_id": 123,
    "is_outdated": None,
    "used_default_profile": None,
    "disclaimer": None,
    "medication": {"guide_id": 9001, "status": "verifying"},
    "lifestyle": {"guide_id": 9002, "status": "generating"},
}

# 7-1 실패
GUIDE_FAILED = {
    "prescription_id": 123,
    "is_outdated": None,
    "used_default_profile": None,
    "disclaimer": DISCLAIMER,
    "medication": {
        "guide_id": 9001,
        "status": "failed",
        "fallback": {
            "drugs": [
                {
                    "prescription_item_id": 502,
                    "drug_name": "가상캡슐",
                    "efficacy": "가상 효능이에요.",
                    "usage_text": "가상 용법이에요.",
                    "precautions": "가상 주의사항이에요.",
                    "data_fetched_at": "2026-11-24",
                }
            ]
        },
    },
    "lifestyle": {"guide_id": 9002, "status": "failed"},
}

# 7-2 다시 시도 (202)
GUIDE_RETRY = {
    "prescription_id": 123,
    "medication": {"guide_id": 9001, "status": "generating"},
    "lifestyle": {"guide_id": 9002, "status": "completed"},
}

# 7-3 내 가이드 목록
GUIDE_LIST = {
    "items": [
        {
            "prescription_id": 123,
            "hospital_name": "가상내과의원",
            "prescribed_date": "2026-11-20",
            "drug_count": 3,
            "status": "completed_with_replacements",
            "is_outdated": False,
            "created_at": "2026-11-20T09:01:10+09:00",
        }
    ],
    "page": 1,
    "size": 20,
    "total": 1,
}

# 7-4 추천 질문
CHAT_SUGGESTIONS = {
    "questions": [
        {"text": "가상정 먹고 술 마셔도 되나요?", "drug_name": "가상정"},
        {"text": "가상캡슐은 식전에 먹어도 되나요?", "drug_name": "가상캡슐"},
        {"text": "함께 피해야 할 음식이 있나요?", "drug_name": None},
    ]
}

# 7-5 대화방 만들기 (201)
CHAT_SESSION = {"session_id": 77, "created_at": "2026-11-20T10:00:00+09:00"}

# 7-6 SSE 이벤트 (meta와 done은 라우터가 붙임). 상황(case)별 가운데 이벤트 목록
CHAT_EVENTS = {
    "normal": [
        ("delta", {"text": "가상진통정은 "}),
        ("delta", {"text": "지금 드시는 약과 함께 드셔도 되는지 "}),
        ("delta", {"text": "의사·약사에게 확인해 주세요."}),
        ("sources", {"items": [{"drug_id": 1204, "name": "의약품개요정보(e약은요): 가상정"}]}),
    ],
    "physical": [
        ("emergency", {"type": "physical", "call": "119", "text": "가슴 통증이 심하면 바로 119에 전화하세요."}),
        ("delta", {"text": "약과 관련해서는 "}),
        ("delta", {"text": "응급 처치를 받은 뒤 의사에게 복용 중인 약을 알려 주세요."}),
        ("sources", {"items": []}),
    ],
    "self_harm": [
        (
            "emergency",
            {
                "type": "self_harm",
                "call": "109",
                "text": "혼자 힘들어하지 마세요. 109에 전화하면 바로 이야기를 들어 드려요.",
            },
        ),
    ],
    "out_of_scope": [
        ("out_of_scope", {"type": "diagnosis", "text": "진단은 의사만 할 수 있어요. 진료 때 의사에게 물어봐 주세요."}),
    ],
    "error": [
        ("delta", {"text": "가상진통정은 "}),
        ("error", {"code": "EXTERNAL_API_ERROR", "message": "답변을 불러오지 못했어요. 다시 보내기를 눌러 주세요"}),
    ],
}
