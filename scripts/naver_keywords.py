"""네이버 검색광고 공식 API(keywordstool)로 월간 검색량을 조회한다.

키는 GitHub Actions Secrets에서만 읽는다. 코드와 결과에 키를 남기지 않는다.
사용: python scripts/naver_keywords.py "키워드1,키워드2,..."
"""
import base64, csv, urllib.error, hashlib, hmac, json, os, sys, time, urllib.parse, urllib.request
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
    q = urllib.parse.urlencode({"hintKeywords": ",".join(batch), "showDetail": "1"})
    req = urllib.request.Request(f"{BASE}{PATH}?{q}", headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["keywordList"]
    except urllib.error.HTTPError as e:
        # 응답 본문(오류 사유)만 출력한다. 요청 헤더나 키는 출력하지 않는다.
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
        raise


def main():
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
