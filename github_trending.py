#!/usr/bin/env python3
"""GitHub Trending 抓取脚本"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

OUTPUT = "/Users/tony/develop/openclaw/gzh/github_trending_today.json"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
}

r = requests.get('https://github.com/trending', headers=headers, timeout=30)
soup = BeautifulSoup(r.text, 'lxml')

repos = []
for article in soup.select('article.Box-row'):
    try:
        # 仓库名
        h2 = article.find('h2')
        if not h2:
            continue
        name_parts = h2.get_text(strip=True).split()
        full_name = '/'.join(part for part in name_parts if part and part != '/') if len(name_parts) >= 2 else ''
        
        # 描述
        desc_el = article.find('p', class_='col-9')
        desc = desc_el.get_text(strip=True) if desc_el else ''
        
        # 语言
        lang_el = article.find('span', itemprop='programmingLanguage')
        lang = lang_el.get_text(strip=True) if lang_el else ''
        
        # stars
        stars_el = article.find('a', href=lambda h: h and h.endswith('/stargazers'))
        stars = stars_el.get_text(strip=True) if stars_el else '0'
        
        # today stars
        today_el = article.find('span', class_='float-sm-right')
        today_stars = today_el.get_text(strip=True) if today_el else '0'
        
        repos.append({
            'name': full_name,
            'desc': desc,
            'lang': lang,
            'stars': stars,
            'today': today_stars
        })
    except Exception as e:
        print(f"  Skip item: {e}")
        continue

output = {
    'date': datetime.now().strftime('%Y-%m-%d'),
    'repos': repos
}

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

# 输出结果（供 cron agent 读取）
print(f"📡 GitHub Trending · {output['date']}")
print(f"共 {len(repos)} 个仓库")
for i, repo in enumerate(repos, 1):
    print(f"\n{i}. {repo['name']}")
    print(f"   {repo['desc']}")
    print(f"   {repo['lang']} | ⭐ {repo['stars']} | {repo['today']}")
