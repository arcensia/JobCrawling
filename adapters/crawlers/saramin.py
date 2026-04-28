import requests
from bs4 import BeautifulSoup

from adapters.crawlers.filters import HEADERS
from core.config import AppConfig


def fetch_saramin(keyword: str, cfg: AppConfig) -> list[dict]:
    results = []
    limit = int(cfg.max_per_site)
    try:
        url = "https://www.saramin.co.kr/zf_user/search/recruit"
        params = {
            "searchType": "search",
            "searchword": keyword,
            "loc_mcd": "101000,102000,108000",
            "exp_cd": "1,2,3",
            "recruitPage": "1",
            "recruitSort": "reg_dt",
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".item_recruit")[:limit]
        for it in items:
            title_a = it.select_one(".area_job .job_tit a")
            company_a = it.select_one(".area_corp .corp_name a")
            cond = it.select_one(".job_condition")
            sector = it.select_one(".job_sector")
            title = title_a.get("title", "").strip() if title_a else ""
            href = title_a.get("href", "") if title_a else ""
            url_full = "https://www.saramin.co.kr" + href if href else ""
            company = company_a.get_text(strip=True) if company_a else ""
            cond_text = cond.get_text(" / ", strip=True) if cond else ""
            sector_text = sector.get_text(" / ", strip=True) if sector else ""
            results.append({
                "site": "사람인",
                "title": title,
                "company": company,
                "location": cond_text,
                "experience": "1~3년",
                "url": url_full,
                "tags": sector_text,
            })
    except Exception as e:
        print(f"[saramin] {keyword} 오류: {e}")
    return results
