"""폰트 약관 페이지의 시점별 지문(해시)을 기록한다.

- robots.txt가 허용하는 페이지만 가져온다.
- 원문은 저장소에 올리지 않는다(저작권). 정규화한 텍스트의 sha256과 길이만 기록한다.
- 내용이 바뀌면 인터넷 아카이브에 스냅샷 저장을 요청해 제3자 시점 증거를 남긴다.
"""
import csv, hashlib, json, re, sys, time, urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

UA = "font-license-history/0.1 (+https://github.com/SmooooooD/font-license-history)"
ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "records"


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace"), r.headers


def allowed(url):
    p = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # robots.txt가 없으면 일반 규칙상 허용
    return rp.can_fetch(UA, url)


def normalize(html):
    t = TextOnly()
    t.feed(html)
    text = " ".join(t.parts)
    return re.sub(r"\s+", " ", text).strip()


def wayback(url):
    try:
        _, headers = get("https://web.archive.org/save/" + url, timeout=120)
        loc = headers.get("Content-Location")
        return "https://web.archive.org" + loc if loc else "requested"
    except Exception as e:
        return f"failed: {type(e).__name__}"


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = []
    with open(ROOT / "sources.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid, url = row["id"], row["official_url"]
            d = RECORDS / sid
            d.mkdir(parents=True, exist_ok=True)
            latest_p = d / "latest.json"
            latest = json.loads(latest_p.read_text()) if latest_p.exists() else None
            rec = {"checked_at": now, "url": url}
            if not allowed(url):
                rec["status"] = "robots_disallowed"
            else:
                try:
                    html, _ = get(url)
                    text = normalize(html)
                    rec.update(status="ok", sha256=hashlib.sha256(text.encode()).hexdigest(), text_length=len(text))
                except Exception as e:
                    rec.update(status=f"error: {type(e).__name__}")
            changed = rec.get("sha256") and (latest is None or latest.get("sha256") != rec["sha256"])
            if changed:
                rec["wayback"] = wayback(url)
                (d / f"{now.replace(':', '')}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
                latest_p.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
            summary.append((sid, rec["status"], "CHANGED" if changed else "same"))
            time.sleep(3)
    for s in summary:
        print(*s)


if __name__ == "__main__":
    sys.exit(main())
