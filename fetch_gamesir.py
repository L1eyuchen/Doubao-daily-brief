# -*- coding: utf-8 -*-
"""
盖世小鸡（GameSir）行业资讯 - GitHub Actions 云版
- 抓取 RSS + HTML，相关性分类，时间窗过滤，去重（seen.json 存仓库）
- 通过飞书群自定义机器人 webhook 推送（环境变量 FEISHU_WEBHOOK）
用法: python fetch_gamesir.py [小时窗]
"""
import sys, io, os, re, json, hashlib, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests, feedparser
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE, "seen.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 24

WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# ---------- 源配置 ----------
RSS_SOURCES = [
    ("IGN",              "https://feeds.ign.com/ign/all",                  "行业"),
    ("IGN中国",          "https://www.ign.com.cn/rss",                    "行业"),
    ("Eurogamer",        "https://www.eurogamer.net/feed",                "行业"),
    ("PC Gamer",         "https://www.pcgamer.com/rss/",                  "行业"),
    ("RockPaperShotgun", "https://www.rockpapershotgun.com/feed",         "行业"),
    ("TheVerge",         "https://www.theverge.com/rss/games/index.xml",  "行业"),
    ("Tomshardware",     "https://www.tomshardware.com/feeds/all",        "硬件"),
    ("IT之家",           "https://www.ithome.com/rss/",                   "硬件"),
]

HTML_SOURCES = [
    ("盖世小鸡官网", "https://www.xiaoji.com/about/", "官方", "xiaoji"),
    ("游民星空-硬件", "https://www.gamersky.com/hardware/", "硬件", "generic"),
    ("3DM新闻", "https://www.3dmgame.com/news/", "行业", "generic"),
]

# ---------- 相关性关键词 ----------
CORE_KW = ["盖世小鸡", "gamesir", "小鸡手柄", "小鸡塔可", "观星者", "启明星", "九尾狐", "天王星", "cyclone", "g7 pro", "g8", "t4", "x5 lite", "x2", "x3"]
INDUSTRY_KW = ["手柄", "controller", "gamepad", "游戏外设", "掌机", "steam deck", "rog ally", "游戏主机", "xbox", "playstation", "switch", "电竞", "esports", "游戏发布会", "state of play"]
HARDWARE_KW = ["显卡", "gpu", "cpu", "主板", "电源", "内存", "ssd", "固态", "显示器", "键盘", "鼠标", "耳机", "机箱", "散热", "外设", "装机", "diy", "pc硬件"]
RIVAL_KW = ["飞智", "北通", "八爪鱼", "墨将", "8bitdo", "dualsense", "scuf", "victrix", "nacon", "turtle beach", "razer", "powera", "xbox elite", "dualshock", "雷蛇", "罗技", "logitech", "雷柏", "盖尔"]

def _hit(text, kws):
    t = text.lower()
    for k in kws:
        if k.isascii():
            if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t):
                return True
        else:
            if k in t:
                return True
    return False

def classify(text):
    if _hit(text, CORE_KW):
        return "核心"
    if _hit(text, RIVAL_KW):
        return "竞品"
    if _hit(text, INDUSTRY_KW):
        return "行业"
    if _hit(text, HARDWARE_KW):
        return "硬件"
    return None

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)

def hk(text):
    return hashlib.md5(re.sub(r"\s+", "", text).lower().encode()).hexdigest()[:12]

def rel_time(published):
    try:
        if hasattr(published, "tm_year"):
            dt = datetime.datetime(*published[:6])
        else:
            return None
        delta = datetime.datetime.now() - dt
        if delta.total_seconds() < 0 or delta.days > 3:
            return None
        if delta.days >= 1:
            return f"{delta.days}天前"
        if delta.seconds >= 3600:
            return f"{delta.seconds // 3600}小时前"
        return f"{max(delta.seconds // 60, 1)}分钟前"
    except Exception:
        return None

def fetch_rss(src):
    name, url, cat = src
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        if r.status_code != 200:
            return out
        fp = feedparser.parse(r.content)
        for e in fp.entries[:40]:
            out.append({"name": name, "cat": cat, "title": e.get("title", "").strip(),
                        "link": e.get("link", ""),
                        "published": e.get("published_parsed") or e.get("updated_parsed")})
    except Exception as ex:
        print(f"[WARN] {name} -> {str(ex)[:60]}", flush=True)
    return out

def fetch_html(src):
    name, url, cat, kind = src
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "html.parser")
        if kind == "xiaoji":
            txt = soup.get_text("\n", strip=True)
            lines = [l.strip() for l in txt.split("\n") if l.strip()]
            date_next = None
            for line in lines:
                dm = re.search(r"(20\d{2}-\d{2}-\d{2})", line)
                if dm:
                    date_next = dm.group(1)
                    continue
                if re.search(r"(上市|发布|开售|联名|正式|上线|代言)", line) and 8 < len(line) < 120:
                    out.append({"name": name, "cat": cat, "title": line, "link": url, "published": date_next})
                    date_next = None
        else:
            seen = set()
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                href = a["href"]
                if not title or len(title) < 8:
                    continue
                if not href.startswith("http"):
                    href = url.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                h = hk(title)
                if h in seen:
                    continue
                seen.add(h)
                out.append({"name": name, "cat": cat, "title": title, "link": href, "published": None})
                if len(out) >= 25:
                    break
    except Exception as ex:
        print(f"[WARN] {name} -> {str(ex)[:60]}", flush=True)
    return out

def build_report():
    items = []
    for s in RSS_SOURCES:
        items.extend(fetch_rss(s))
    for s in HTML_SOURCES:
        items.extend(fetch_html(s))

    seen = load_seen()
    now = datetime.datetime.now()
    groups = {"核心": [], "行业": [], "硬件": [], "竞品": []}
    for it in items:
        cat = classify(it["title"])
        if not cat:
            continue
        h = hk(it["title"])
        if h in seen:
            continue
        if it["published"]:
            try:
                if isinstance(it["published"], str):
                    dt = datetime.datetime.strptime(it["published"], "%Y-%m-%d")
                else:
                    dt = datetime.datetime(*it["published"][:6])
                if (now - dt).total_seconds() > HOURS * 3600:
                    continue
            except Exception:
                pass
        seen[h] = 1
        rt = rel_time(it["published"]) if it["published"] else None
        groups[cat].append({"title": it["title"], "link": it["link"], "src": it["name"], "rt": rt})

    order = ["核心", "行业", "硬件", "竞品"]
    icons = {"核心": "🔥", "行业": "📰", "硬件": "🖥", "竞品": "🆚"}
    total = sum(len(groups[k]) for k in order)
    lines = [f"【盖世小鸡·行业简报】{now.strftime('%m-%d %H:%M')}（近{HOURS}h）", f"共 {total} 条相关资讯\n"]
    for k in order:
        if not groups[k]:
            continue
        lines.append(f"{icons[k]} {k}")
        for it in groups[k][:8]:
            t = it["title"][:45] + ("…" if len(it["title"]) > 45 else "")
            rts = f"（{it['rt']}）" if it["rt"] else ""
            lines.append(f"· {t} {rts}")
            lines.append(f"  {it['link']}")
        lines.append("")
    if total == 0:
        lines.append("本次没有新的相关资讯。")

    save_seen(seen)
    return "\n".join(lines), total

def push(content):
    if not WEBHOOK:
        print("[NO_WEBHOOK] 未配置 FEISHU_WEBHOOK", flush=True)
        return False
    # 飞书自定义机器人 webhook，使用富文本 post 格式，支持换行与链接
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        r = requests.post(WEBHOOK, json=payload, timeout=15)
        ok = r.status_code == 200
        print(f"[PUSH] status={r.status_code} resp={r.text[:200]}", flush=True)
        return ok
    except Exception as ex:
        print(f"[PUSH_ERR] {str(ex)[:100]}", flush=True)
        return False

if __name__ == "__main__":
    content, total = build_report()
    print(content, flush=True)
    if total == 0:
        print("[SKIP] 无新内容", flush=True)
    else:
        push(content)
