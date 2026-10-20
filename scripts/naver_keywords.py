"""네이버 검색광고 공식 API(keywordstool)로 월간 검색량을 조회한다.

키는 GitHub Actions Secrets에서만 읽는다. 코드와 결과에 키를 남기지 않는다.
사용: python scripts/naver_keywords.py "키워드1,키워드2,..."
"""
import base64, csv, http.client, hashlib, hmac, json, os, sys, time, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

BASE = "https://api.searchad.naver.com"
PATH = "/keywordstool"
ROOT = Path(__file__).resolve().parent.parent


def headers():
    ts = str(int(time.time() * 1000))
    secret = os.environ["NAVER_SECRET_KEY"].strip().encode()
    sig = base64.b64encode(hmac.new(secret, f"{ts}.GET.{PATH}".encode(), hashlib.sha256).digest()).decode()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": os.environ["NAVER_ACCESS_LICENSE"].strip(),
        "X-Customer": os.environ["NAVER_CUSTOMER_ID"].strip(),
        "X-Signature": sig,
    }


def query(batch):
    # urllib.request는 헤더 이름을 X-signature처럼 바꿔 버려 네이버가 서명을 못 읽는다.
    # http.client는 헤더 이름을 그대로 보내므로 이것을 쓴다.
    q = urllib.parse.urlencode({"hintKeywords": ",".join(batch), "showDetail": "1"})
    conn = http.client.HTTPSConnection("api.searchad.naver.com", timeout=30)
    conn.request("GET", f"{PATH}?{q}", headers=headers())
    r = conn.getresponse()
    body = r.read().decode("utf-8", "replace")
    if r.status != 200:
        # 응답 본문(오류 사유)만 출력한다. 요청 헤더나 키는 출력하지 않는다.
        print(f"HTTP {r.status}: {body[:500]}")
        sys.exit(1)
    return json.loads(body)["keywordList"]


def diagnose():
    """키 값은 출력하지 않고, 형태(길이·숫자 여부)만 출력해 잘못 넣은 칸이 있는지 본다."""
    for name in ("NAVER_CUSTOMER_ID", "NAVER_ACCESS_LICENSE", "NAVER_SECRET_KEY"):
        v = os.environ.get(name, "")
        print(f"{name}: length={len(v.strip())}, digits_only={v.strip().isdigit()}, "
              f"had_whitespace={v != v.strip()}, empty={not v.strip()}")


def main():
    diagnose()
    words = [w.replace(" ", "") for w in sys.argv[1].split(",") if w.strip()]
    rows = []
    for i in range(0, len(words), 5):  # API는 한 번에 힌트 키워드 5개까지
        for k in query(words[i:i + 5]):
            rows.append({
                "hint": ",".join(words[i:i + 5]),
                "keyword": k["relKeyword"],
                "pc": k["monthlyPcQcCnt"],
                "mobile": k["monthlyMobileQcCnt"],
                "comp": k.get("compIdx", ""),
            })
        time.sleep(1)
    out = ROOT / "data" / "keywords" / f"{date.today().isoformat()}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["hint", "keyword", "pc", "mobile", "comp"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
