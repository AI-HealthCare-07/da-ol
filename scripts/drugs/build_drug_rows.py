"""받아 둔 공공데이터(JSON)를 drugs 테이블 한 줄 모양으로 바꿔 저장.

- DB 없이 돌아갑니다. 결과는 final_project/data/processed/에 JSON Lines(한 줄 = 약 하나)로 저장합니다.
- 대상: 허가 상세정보 중 CANCEL_NAME이 '정상'인 약.
- 설명 글: e약은요에 있는 약은 e약은요, 없으면 허가 상세정보.
- item_name_norm은 normalize_drug_name()(PR #25) 머지 후 적재할 때 채웁니다.

실행: python3 scripts/drugs/build_drug_rows.py
"""

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FETCHED = "20261124"  # 데이터를 받은 날 (파일 이름의 날짜)
RAW_DIR = Path.home() / "Documents" / "final_project" / "data" / "raw"
OUT_DIR = Path.home() / "Documents" / "final_project" / "data" / "processed"


NOT_ORAL_FORM = re.compile(
    r"주사|바이알|앰플|수액|프리필드|연고|크림(?!색)|로션|패취|패치|플라스터|카타플라스마|첩부"
    r"|점안제|점안액|점안용|점이제|점이액|점비제|점비액|점비용|안약|좌제|좌약|질정|흡입"
    r"|에어로솔|에어로졸|스프레이|분무|외용|가글|양치|관장|파스(?!텔)|고약|경고제|샴푸|소독"
    r"|기체|가스|투석|관류|면봉|겔제"
)
ORAL_FORM = re.compile(
    r"정제|코팅정|당의정|제피정|캡슐|캅셀|시럽|현탁|과립|세립|산제|가루|츄어블|트로키"
    r"|구강용해|내용액|내복|경구|환제|엑스제|연조엑스|드링크"
)
NOT_ORAL_NAME = re.compile(
    r"주사|주\d|주$|주\(|연고|크림(?!색)|로션|패취|패치|플라스타|점안|안약|좌제|좌약|흡입"
    r"|스프레이|에어로솔|에어로졸|가글|겔\d|겔\(|겔$"
)
ORAL_NAME = re.compile(r"정$|정\(|정\d|캡슐|캅셀|시럽|현탁|과립|세립|산$|산\(|환$|환\(|드링크")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean_html(text: str) -> str:
    """글 안의 <p>, <td> 같은 표시를 지우고 &nbsp; 같은 기호를 글자로 바꿉니다."""
    text = re.sub(r"</td>\s*", " | ", text)
    text = re.sub(r"</tr>|</p>|<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip(" |") for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def doc_to_text(doc: str | None) -> str | None:
    """허가 상세정보의 <DOC> 글에서 제목과 문단 글만 뽑습니다."""
    if not doc:
        return None
    root = ET.fromstring(doc)
    parts = []
    for el in root.iter():
        if el.tag == "ARTICLE" and el.get("title"):
            parts.append(el.get("title").strip())
        elif el.tag == "PARAGRAPH" and el.text:
            parts.append(clean_html(el.text))
    text = "\n".join(p for p in parts if p)
    return text or None


def clean_ingredients(raw: str | None) -> str | None:
    """'[M246033]암로디핀캄실산염|[M249673]로사르탄칼륨' → '암로디핀캄실산염, 로사르탄칼륨'"""
    names = []
    for part in (raw or "").split("|"):
        name = re.sub(r"\[[^\]]*\]", "", part).strip()
        if name and name not in names:
            names.append(name)
    return ", ".join(names) or None


def guess_is_oral(name: str | None, chart: str | None) -> bool | None:
    """먹는 약이면 True, 아니면 False, 모르면 None(회원 확인)."""
    name = (name or "").strip()
    chart = chart or ""
    if NOT_ORAL_FORM.search(chart):
        return False
    if ORAL_FORM.search(chart):
        return True
    if NOT_ORAL_NAME.search(name):
        return False
    if ORAL_NAME.search(name):
        return True
    return None


def to_date(value: str | None) -> str | None:
    """'20260212' 또는 '2026-02-12' → '2026-02-12'"""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 8:
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def text_or_none(value: str | None) -> str | None:
    """앞뒤 빈칸·빈 줄을 지우고, 비어 있으면 None."""
    return (value or "").strip() or None


def join_texts(*texts: str | None) -> str | None:
    parts = [t.strip() for t in texts if t and t.strip()]
    return "\n\n".join(parts) or None


def latest_easy_by_seq(easy_items: list) -> dict:
    """e약은요에 같은 약이 여러 줄이면 수정일(updateDe)이 가장 최근인 줄만 남깁니다."""
    result = {}
    for item in easy_items:
        seq = item.get("itemSeq")
        if not seq:
            continue
        if seq not in result or (item.get("updateDe") or "") > (result[seq].get("updateDe") or ""):
            result[seq] = item
    return result


def build_row(detail: dict, easy: dict | None, image_url: str | None, fetched_date: str) -> dict:
    row = {
        "item_seq": detail["ITEM_SEQ"],
        "item_name": (detail.get("ITEM_NAME") or "").strip(),
        "ingredient_name": clean_ingredients(detail.get("MAIN_ITEM_INGR")),
        "company": text_or_none(detail.get("ENTP_NAME")),
        "is_oral": guess_is_oral(detail.get("ITEM_NAME"), detail.get("CHART")),
        "is_otc": {"일반의약품": True, "전문의약품": False}.get(detail.get("ETC_OTC_CODE")),
        "data_fetched_at": fetched_date,
    }
    if easy:
        row.update(
            efficacy=text_or_none(easy.get("efcyQesitm")),
            usage_text=text_or_none(easy.get("useMethodQesitm")),
            precautions=join_texts(easy.get("atpnWarnQesitm"), easy.get("atpnQesitm"), easy.get("intrcQesitm")),
            side_effects=text_or_none(easy.get("seQesitm")),
            storage_method=text_or_none(easy.get("depositMethodQesitm")),
            image_url=easy.get("itemImage") or image_url,
            data_source="easy_drug",
            source_updated_at=to_date(easy.get("updateDe")),
        )
    else:
        row.update(
            efficacy=doc_to_text(detail.get("EE_DOC_DATA")),
            usage_text=doc_to_text(detail.get("UD_DOC_DATA")),
            precautions=doc_to_text(detail.get("NB_DOC_DATA")),
            side_effects=None,
            storage_method=text_or_none(detail.get("STORAGE_METHOD")),
            image_url=image_url,
            data_source="permit",
            source_updated_at=to_date(detail.get("CHANGE_DATE")),
        )
    return row


def pick_latest_pages(detail_dir: Path) -> tuple[dict, int]:
    """품목기준코드마다 변경일(CHANGE_DATE)이 가장 최근인 줄이 든 페이지 파일 이름을 고릅니다.
    같은 약이 두 페이지에 들어간 경우(받는 동안 페이지가 밀림)를 거르기 위해서예요."""
    best = {}
    seen = 0
    for page in sorted(detail_dir.glob("page_*.json")):
        for detail in load_json(page):
            if detail.get("CANCEL_NAME") != "정상":
                continue
            seen += 1
            seq = detail["ITEM_SEQ"]
            changed = detail.get("CHANGE_DATE") or ""
            if seq not in best or changed > best[seq][0]:
                best[seq] = (changed, page.name)
    return best, seen


def main() -> int:
    fetched_date = to_date(FETCHED)
    easy_by_seq = latest_easy_by_seq(load_json(RAW_DIR / f"easy_drug_{FETCHED}.json"))
    permit_list = load_json(RAW_DIR / f"permit_{FETCHED}.json")
    image_by_seq = {r["ITEM_SEQ"]: r.get("BIG_PRDT_IMG_URL") or None for r in permit_list}
    listed = {r["ITEM_SEQ"] for r in permit_list if r.get("CANCEL_NAME") == "정상"}

    detail_dir = RAW_DIR / f"permit_detail_{FETCHED}"
    best_page, seen = pick_latest_pages(detail_dir)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"drugs_rows_{FETCHED}.jsonl"
    counts = {"rows": 0, "easy_drug": 0, "permit": 0, "oral_true": 0, "oral_false": 0, "oral_none": 0}
    written = set()
    with out.open("w", encoding="utf-8") as f:
        for page in sorted(detail_dir.glob("page_*.json")):
            for detail in load_json(page):
                if detail.get("CANCEL_NAME") != "정상":
                    continue
                seq = detail["ITEM_SEQ"]
                if seq in written or best_page[seq][1] != page.name:
                    continue
                written.add(seq)
                row = build_row(detail, easy_by_seq.get(seq), image_by_seq.get(seq), fetched_date)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts["rows"] += 1
                counts[row["data_source"]] += 1
                counts[{True: "oral_true", False: "oral_false", None: "oral_none"}[row["is_oral"]]] += 1

    print(f"저장 완료: {out}")
    print(counts)
    print(f"중복으로 거른 줄: {seen - len(best_page)}개")
    print(f"목록에는 있는데 상세정보에 없는 약: {len(listed - best_page.keys())}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
