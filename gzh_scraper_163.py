#!/usr/bin/env python3
"""
微信公众号文章抓取脚本（网易源）
使用网易(163.com)获取公众号过去24小时的文章

采集源：https://www.163.com/dy/media/T1658526449605.html (记忆承载网易号)
此网易号覆盖了记忆承载、记忆承载3、西风的罗盘、人间罗盘的全部文章

输出：/Users/tony/develop/openclaw/gzh/YYYY/MM/DD/title.md
"""

import requests
from bs4 import BeautifulSoup
import re
import os
import json
import time
from datetime import datetime, timedelta

# ===== 配置 =====
BASE_DIR = "/Users/tony/develop/openclaw/gzh"
STATE_FILE = os.path.join(BASE_DIR, "gzh_state.json")

# 网易号作者页（记忆承载公众号在网易的镜像，覆盖全部4个公众号）
AUTHOR_PAGE = "https://www.163.com/dy/media/T1658526449605.html"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def load_state():
    ensure_dir(BASE_DIR)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"fetched_urls": {}, "last_check": {}}

def save_state(state):
    ensure_dir(BASE_DIR)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def fetch_article_list():
    """从网易作者页解析文章列表（含准确发布时间）"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        r = session.get(AUTHOR_PAGE, timeout=20)
        r.encoding = 'utf-8'
    except Exception as e:
        print(f"  ERROR fetching author page: {e}")
        return []
    
    soup = BeautifulSoup(r.text, 'lxml')
    articles = []
    seen_urls = set()
    
    # 遍历文章列表项
    for item in soup.select('li.js-item.item'):
        try:
            # 标题和链接
            title_el = item.select_one('a.title')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            url = title_el.get('href', '')
            if not url or not title:
                continue
            
            # 标准化URL
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = 'https://www.163.com' + url
            # 去掉追踪参数
            url = url.split('?')[0]
            
            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # 发布时间
            time_el = item.select_one('span.time')
            pub_time = None
            if time_el:
                time_text = time_el.get_text(strip=True)
                try:
                    pub_time = datetime.strptime(time_text, '%Y-%m-%d %H:%M')
                except:
                    pass
            
            if pub_time:
                articles.append({
                    "title": title,
                    "url": url,
                    "pub_time": pub_time,
                })
        except Exception as e:
            print(f"  Warning: error parsing item: {e}")
            continue
    
    return articles

def fetch_article_content(session, url):
    """从网易文章页提取标题和正文"""
    try:
        r = session.get(url, timeout=20)
        r.encoding = 'utf-8'
    except Exception as e:
        print(f"  ERROR fetch: {e}")
        return None, None
    
    soup = BeautifulSoup(r.text, 'lxml')
    
    # 标题
    title_el = soup.find('h1') or soup.find('title')
    title = title_el.get_text(strip=True) if title_el else None
    if title:
        # 清理标题，去掉网站后缀
        title = re.sub(r'\s*[-–—|_].*$', '', title)
    
    # 正文
    article_text = ""
    
    # 尝试多个选择器
    for selector in ['.post_body', '.article-content', '.article-body', '.content',
                     '#content', 'article', 'div[class*="content"]', 'div[class*="article"]']:
        content_div = soup.select_one(selector)
        if content_div:
            # 收集段落
            paragraphs = []
            for tag in content_div.find_all(['p', 'section']):
                t = tag.get_text(strip=True)
                if t and len(t) > 10:
                    # 过滤广告/引导关注
                    skip_keywords = ['关注公众号', '微信扫一扫', '小程序', '阅读原文',
                                     '将本篇文章', '分享收藏', '点赞在看']
                    if not any(kw in t for kw in skip_keywords):
                        paragraphs.append(t)
            
            if paragraphs:
                article_text = '\n\n'.join(paragraphs)
                if len(article_text) > 200:
                    break
    
    # 备用：提取页面主体文本
    if len(article_text) < 100:
        # 移除脚本/样式
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        body = soup.find('body')
        if body:
            lines = [l.strip() for l in body.get_text('\n', strip=True).split('\n') 
                    if l.strip() and len(l.strip()) > 30]
            article_text = '\n\n'.join(lines[:50])  # 取前50行
    
    return title, article_text

def save_article(title, content, pub_time):
    """保存文章：按 YYYY/MM/DD/标题.md 组织"""
    year = pub_time.strftime("%Y")
    month = pub_time.strftime("%m")
    day = pub_time.strftime("%d")
    date_str = pub_time.strftime("%Y-%m-%d")
    
    safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)[:80]
    save_dir = os.path.join(BASE_DIR, year, month, day)
    ensure_dir(save_dir)
    
    filepath = os.path.join(save_dir, f"{safe_title}.md")
    if os.path.exists(filepath):
        return None
    
    md = f"# {title}\n\n"
    md += f"- **时间**: {pub_time.strftime('%Y-%m-%d %H:%M')}\n"
    md += f"- **来源**: 记忆承载（网易号）\n"
    md += f"- **抓取**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    md += "\n---\n\n"
    md += content
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md)
    
    return filepath

def main():
    print(f"\n{'='*60}")
    now = datetime.now()
    print(f"📡 公众号抓取（网易源）| {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    state = load_state()
    fetched_urls = state.get("fetched_urls", {})
    
    print(f"\n📋 获取文章列表...")
    articles = fetch_article_list()
    print(f"  共 {len(articles)} 篇文章")
    
    # 筛选24小时内
    cutoff = now - timedelta(hours=24)
    recent = [a for a in articles if a['pub_time'] >= cutoff]
    print(f"  过去24小时: {len(recent)} 篇")
    
    if not recent:
        print("\n⏭ 无新文章")
        state["last_check"] = {"time": now.isoformat(), "saved": 0}
        save_state(state)
        return
    
    print()
    session = requests.Session()
    session.headers.update(HEADERS)
    
    saved = 0
    errors = 0
    
    for art in recent:
        title = art["title"]
        url = art["url"]
        pub_time = art["pub_time"]
        
        # 去重
        dedup_key = url
        if dedup_key in fetched_urls:
            continue
        
        print(f"  📥 {title[:50]}...", end=" ", flush=True)
        
        content_title, content = fetch_article_content(session, url)
        if not content or len(content) < 50:
            print("❌")
            errors += 1
            continue
        
        fp = save_article(content_title or title, content, pub_time)
        if fp:
            print("✅")
            saved += 1
            fetched_urls[dedup_key] = {
                "title": content_title or title,
                "url": url,
                "pub_time": pub_time.strftime('%Y-%m-%d %H:%M'),
                "fetched_at": datetime.now().isoformat()
            }
        else:
            print("⏭")
        
        time.sleep(0.3)
    
    state["fetched_urls"] = fetched_urls
    state["last_check"] = {"time": now.isoformat(), "saved": saved, "errors": errors}
    save_state(state)
    
    print(f"\n{'='*60}")
    print(f"✅ 完成 | 保存: {saved} | 跳过: {len(recent)-saved-errors} | 失败: {errors}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
