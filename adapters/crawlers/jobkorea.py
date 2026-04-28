import requests
from urllib.parse import quote
from bs4 import BeautifulSoup

from adapters.crawlers.filters import HEADERS
from core.config import AppConfig


def fetch_jobkorea(keyword: str, cfg: AppConfig) -> list[dict]:
    results = []
    limit = int(cfg.max_per_site)
    try:
        url = f"https://www.jobkorea.co.kr/Search/?stext={quote(keyword)}&careerType=1&careerMin=1&careerMax=3&local=I000"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("ul.clear > li.list-post, li.list-post")[:limit]
        for it in items:
            title_a = it.select_one("a.title")
            company_a = it.select_one("a.name") or it.select_one(".post-list-corp a")
            etc = it.select_one(".option, .etc")
            title = title_a.get_text(strip=True) if title_a else ""
            href = title_a.get("href", "") if title_a else ""
            url_full = "https://www.jobkorea.co.kr" + href if href.startswith("/") else href
            company = company_a.get_text(strip=True) if company_a else ""
            etc_text = etc.get_text(" / ", strip=True) if etc else ""
            if not title:
                continue
            results.append({
                "site": "잡코리아",
                "title": title,
                "company": company,
                "location": etc_text,
                "experience": "1~3년",
                "url": url_full,
                "tags": keyword,
            })
    except Exception as e:
        print(f"[jobkorea] {keyword} 오류: {e}")
    return results
