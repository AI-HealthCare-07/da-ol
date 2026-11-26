"""테스트 처방 이미지(PR #24, case01~13)를 실제 CLOVA OCR로 읽어 '가린 줄'을 케이스별로 저장합니다.

OCR 단계(① 읽기 → 줄로 묶기 → ② 가리기)만 실제로 돌립니다. LLM 정리·표현 사전·약 매칭은 아직 없어서 하지 않습니다.
결과는 저장소 밖 폴더에 저장하므로 git에 섞이지 않습니다.

준비
  1) feat/clova-ocr-client 브랜치(PR #33)에서 실행 (app/services/clova_ocr.py 필요)
  2) 저장소 루트의 .env에 CLOVA_OCR_URL, CLOVA_OCR_SECRET 입력 (키는 .env에만, 커밋 금지)

실행 (저장소 루트에서)
  uv run python scripts/ocr/run_clova_test_prescriptions.py
  uv run python scripts/ocr/run_clova_test_prescriptions.py --cases 10 11 12        # 일부만
  uv run python scripts/ocr/run_clova_test_prescriptions.py --save-raw              # CLOVA 원본 응답도 저장

이미지는 기본으로 git 브랜치 origin/docs/test-prescriptions-part2에서 바로 읽습니다(작업 폴더에 파일을 꺼내지 않음).
폴더에서 읽으려면 --images-dir docs/test-prescriptions 처럼 지정하세요.

개인정보: 테스트 처방 이미지는 모두 가상 데이터라 결과를 저장해도 됩니다.
**실제 처방전 사진으로는 이 스크립트를 돌리지 마세요.** 특히 --save-raw 결과에는 가리기 전 원문이 들어 있습니다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app.services.clova_ocr import ClovaOcrClient, ClovaOcrError, parse_clova_response  # noqa: E402
from app.services.scan_service import NEEDS_CHECK_BELOW, OcrLine, is_no_text, mask_lines  # noqa: E402

DEFAULT_REF = "origin/docs/test-prescriptions-part2"
IMAGE_PATH_IN_REPO = "docs/test-prescriptions/case{n:02d}.png"

# 케이스별로 OCR 줄에서 찾아볼 약 이름(공백 무시). PR #24 README 기준.
EXPECTED_DRUGS: dict[int, list[str]] = {
    1: ["아모잘탄정", "리바로정"],
    2: ["자누메트정", "알마겔정"],
    3: ["넥시움정", "무코스타정"],
    4: ["코대원포르테시럽", "펠루비정", "무코스타정"],
    5: ["란스톤엘에프디티정", "모사프리드정", "하루날디정"],
    6: ["쎄레브렉스캡슐", "타이레놀정"],
    7: ["노바스크정", "다이아벡스정", "크레스토정", "아스피린프로텍트정"],
    8: ["다올비타플러스정", "알마겔정"],
    9: ["타이레놀8시간이알서방정", "스티렌투엑스정"],
    10: ["트라젠타정", "아토르바스타틴정", "가스모틴정"],
    11: ["세토펜정", "베아제정"],
    12: ["아모잘탄정", "무코스타정"],
    13: ["히알유니점안액", "에스로반연고"],
}
# 가려져야 하는 가상 개인정보(원문). 가린 줄에 남아 있으면 '안 가려짐'으로 표시합니다.
MUST_BE_MASKED: dict[int, list[str]] = {
    11: ["053-123-4567", "김다올"],
    12: ["김다올", "000101-3000000", "010-0000-0000"],
}


def load_dotenv(path: Path) -> None:
    """.env의 KEY=VALUE를 환경 변수로 읽습니다(이미 있는 값은 덮어쓰지 않음)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_image(n: int, images_dir: Path | None, ref: str) -> bytes:
    if images_dir is not None:
        return (images_dir / f"case{n:02d}.png").read_bytes()
    spec = f"{ref}:{IMAGE_PATH_IN_REPO.format(n=n)}"
    result = subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise FileNotFoundError(f"{spec} 를 읽지 못했어요. 먼저 `git fetch origin`을 해 주세요.")
    return result.stdout


def line_to_dict(line: OcrLine) -> dict:
    return {
        "line_idx": line.line_idx,
        "text": line.text,
        "min_confidence": round(min((w.confidence for w in line.words), default=0.0), 3),
        "words": [[w.text, round(w.confidence, 3)] for w in line.words],
    }


def nospace(s: str) -> str:
    return "".join(s.split())


def check_case(n: int, masked: list[OcrLine], raw_lines: list[OcrLine]) -> dict:
    joined = nospace(" ".join(line.text for line in masked))
    found = {name: nospace(name) in joined for name in EXPECTED_DRUGS.get(n, [])}
    leaks = [v for v in MUST_BE_MASKED.get(n, []) if nospace(v) in joined]
    low = [line.line_idx for line in masked if any(w.confidence < NEEDS_CHECK_BELOW for w in line.words)]
    changed = sum(1 for a, b in zip(raw_lines, masked, strict=True) if a.text != b.text)
    return {
        "lines": len(masked),
        "no_text": is_no_text(masked),
        "drugs_found": found,
        "masked_lines": changed,
        "not_masked": leaks,
        "low_confidence_lines": low,
    }


async def run_case(client: ClovaOcrClient, http: httpx.AsyncClient, image: bytes) -> tuple[dict, list[OcrLine]]:
    body = client.build_request_body(image)
    url, secret = os.environ["CLOVA_OCR_URL"], os.environ["CLOVA_OCR_SECRET"]
    last_error: Exception | None = None
    for attempt in range(2):  # 실패하면 한 번만 다시
        try:
            resp = await http.post(url, json=body, headers={"X-OCR-SECRET": secret})
            if resp.status_code != 200:
                raise ClovaOcrError(f"HTTP {resp.status_code}")
            data = resp.json()
            return data, parse_clova_response(data)
        except (httpx.HTTPError, ClovaOcrError, ValueError) as e:
            last_error = e
            await asyncio.sleep(1 + attempt)
    raise ClovaOcrError(f"CLOVA 호출 실패: {type(last_error).__name__}: {last_error}")


def write_summary(out: Path, results: dict[int, dict]) -> None:
    rows = [
        "# 테스트 처방 CLOVA OCR 결과 (OCR 단계만)",
        "",
        f"- 실행: {datetime.now():%Y-%m-%d %H:%M}",
        "- 약 이름 찾기는 가린 줄 전체에서 공백을 지우고 비교했어요(줄바꿈으로 쪼개져도 찾음).",
        f"- 신뢰도 낮은 줄: 단어 하나라도 {NEEDS_CHECK_BELOW} 미만인 줄(line_idx).",
        "",
        "| 케이스 | 줄 수 | 약 이름 찾음 | 못 찾은 약 | 가린 줄 | 안 가려진 개인정보 | 신뢰도 낮은 줄 | 비고 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for n, r in sorted(results.items()):
        if "error" in r:
            rows.append(f"| case{n:02d} | - | - | - | - | - | - | ❌ {r['error']} |")
            continue
        found = r["drugs_found"]
        missing = [k for k, v in found.items() if not v]
        note = "글자 없음(no_text)" if r["no_text"] else ""
        rows.append(
            f"| case{n:02d} | {r['lines']} | {sum(found.values())}/{len(found)} | {', '.join(missing) or '-'} "
            f"| {r['masked_lines']} | {', '.join(r['not_masked']) or '-'} | {r['low_confidence_lines'] or '-'} | {note} |"
        )
    rows += ["", "케이스별 가린 줄은 `caseNN_lines.json`에 있어요."]
    (out / "summary.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=int, nargs="*", default=list(range(1, 14)), help="돌릴 케이스 번호(기본 1~13)")
    parser.add_argument("--ref", default=DEFAULT_REF, help=f"이미지를 읽을 git 브랜치(기본 {DEFAULT_REF})")
    parser.add_argument("--images-dir", type=Path, default=None, help="git 대신 이 폴더에서 caseNN.png를 읽음")
    parser.add_argument("--out", type=Path, default=None, help="결과 폴더(기본: 저장소 밖 ../daol_ocr_runs/날짜시각)")
    parser.add_argument("--save-raw", action="store_true", help="CLOVA 원본 응답도 저장(가리기 전 글자 포함)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.environ.get("CLOVA_OCR_URL") or not os.environ.get("CLOVA_OCR_SECRET"):
        print("❌ .env에 CLOVA_OCR_URL, CLOVA_OCR_SECRET을 넣어 주세요.")
        return 1

    out = args.out or ROOT.parent / "daol_ocr_runs" / datetime.now().strftime("%Y%m%d_%H%M")
    out.mkdir(parents=True, exist_ok=True)
    print(f"결과 폴더: {out}")

    results: dict[int, dict] = {}
    async with httpx.AsyncClient(timeout=30) as http:
        client = ClovaOcrClient(os.environ["CLOVA_OCR_URL"], os.environ["CLOVA_OCR_SECRET"], http_client=http)
        for n in args.cases:
            name = f"case{n:02d}"
            try:
                image = read_image(n, args.images_dir, args.ref)
                data, raw_lines = await run_case(client, http, image)
            except (FileNotFoundError, ClovaOcrError) as e:
                results[n] = {"error": str(e)}
                print(f"  {name}: ❌ {e}")
                continue

            masked = mask_lines(raw_lines)  # run_scan_job ②와 같은 가리기
            check = check_case(n, masked, raw_lines)
            results[n] = check
            (out / f"{name}_lines.json").write_text(
                json.dumps(
                    {"case": n, "check": check, "lines": [line_to_dict(x) for x in masked]},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if args.save_raw:
                (out / f"{name}_clova_raw.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            found = check["drugs_found"]
            print(
                f"  {name}: 줄 {check['lines']}개, 약 이름 {sum(found.values())}/{len(found)}"
                + (f", 안 가려짐 {check['not_masked']}" if check["not_masked"] else "")
            )
            await asyncio.sleep(0.5)  # 연속 호출 간격

    write_summary(out, results)
    print(f"요약: {out / 'summary.md'}")
    return 0 if all("error" not in r for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
