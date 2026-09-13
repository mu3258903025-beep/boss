# -*- coding: utf-8 -*-
"""
BOSS 直聘岗位采集 + 清洗 + 筛选项目（本地网页版）

零第三方依赖，只用 Python 标准库。
- 上传 / 加载一份岗位 CSV（公司、岗位、城市、薪资、经验、学历、岗位描述...）
- 自动清洗：薪资拆成「元/月」上下限、城市归一、去重、空值标记
- 按城市 / 最低薪资 / 技能要求 / 关键词 筛选
- 一键调用本地 Ollama（qwen3.5:9b）从岗位描述里提取技能要求
- 导出清洗后的 CSV

合规：仅处理你提供的公开岗位数据，不主动爬取、不抓取任何隐私信息。
"""

import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # 允许 import 同目录的 fetch_boss 等模块
PORT = 8090
OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
BOOT_LOG = os.path.join(HERE, "_boot.txt")


def log_boot(msg):
    with open(BOOT_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# 用来做基础技能命中的关键词（即使不调大模型也能筛）
SKILL_KEYWORDS = [
    "Python", "SQL", "Java", "Excel", "爬虫", "Scrapy", "Selenium", "Playwright",
    "数据分析", "Linux", "正则", "pandas", "NumPy", "Hadoop", "Spark", "Tableau",
    "MySQL", "Redis", "Docker", "AWS", "机器学习", "可视化", "Flask", "BeautifulSoup",
    "requests", "数据仓库",
]

# 城市白名单（用于把「广州·天河区」归一成「广州」）
KNOWN_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "苏州",
    "重庆", "天津", "长沙", "郑州", "青岛", "厦门", "宁波", "东莞", "佛山", "合肥",
    "远程",
]


# ----------------------------- 清洗逻辑 -----------------------------

def parse_salary(text):
    """把各种薪资格式转成「元/月」的上下限。

    返回 (min_month, max_month, unit)。解析不出返回 (None, None, '')。
    """
    if not text:
        return None, None, ""
    t = str(text).strip()
    if "面议" in t or "薪资" in t and "议" in t:
        return None, None, "面议"
    if not re.search(r"\d", t):
        return None, None, t

    low = t.lower()
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if not nums:
        return None, None, t

    def f(x):
        return float(x)

    # 日薪：元/天
    if "天" in t or "/天" in low:
        a, b = f(nums[0]), f(nums[1]) if len(nums) > 1 else f(nums[0])
        mul = 21.75  # 月计薪天数
        return int(a * mul), int(b * mul), "元/天"
    # 万/月
    if "万" in t:
        a, b = f(nums[0]), f(nums[1]) if len(nums) > 1 else f(nums[0])
        return int(a * 10000), int(b * 10000), "万/月"
    # K（千）/月
    if "k" in low:
        a, b = f(nums[0]), f(nums[1]) if len(nums) > 1 else f(nums[0])
        return int(a * 1000), int(b * 1000), "K/月"
    # 纯数字 + 元（默认按月）
    if "元" in t:
        a, b = f(nums[0]), f(nums[1]) if len(nums) > 1 else f(nums[0])
        return int(a), int(b), "元/月"
    # 兜底：当成「千」
    a, b = f(nums[0]), f(nums[1]) if len(nums) > 1 else f(nums[0])
    return int(a * 1000), int(b * 1000), "K/月"


def normalize_city(text):
    if not text:
        return ""
    t = str(text).strip()
    # 优先白名单匹配
    for c in KNOWN_CITIES:
        if c in t:
            return c
    # 否则按分隔符取第一段
    for sep in ["·", "-", "—", " ", "/"]:
        if sep in t:
            return t.split(sep)[0].strip()
    return t


def active_days(text):
    """把 HR 活跃度文案转成「大约多少天内活跃」，越小越活跃。取不到→999。"""
    s = (text or "").strip()
    if not s:
        return 999
    if "刚刚" in s or "今日" in s or "随时" in s or "在线" in s:
        return 0
    if "本周" in s or "一周内" in s or "7日内" in s:
        return 7
    if "本月" in s:
        return 30
    if "半年" in s:
        return 180
    m = re.search(r"(\d+)\s*(?:天|日)内", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*月内", s)
    if m:
        return int(m.group(1)) * 30
    return 999


def basic_skills(jd_text):
    if not jd_text:
        return []
    found = []
    low = str(jd_text).lower()
    for kw in SKILL_KEYWORDS:
        if kw.lower() in low:
            found.append(kw)
    return found


def clean_rows(raw_rows):
    """对原始行做清洗，返回 (cleaned_rows, stats)。"""
    seen = set()
    cleaned = []
    dup_count = 0
    for r in raw_rows:
        company = (r.get("公司名称") or "").strip()
        title = (r.get("岗位名称") or "").strip()
        city_raw = (r.get("城市") or "").strip()
        salary_raw = (r.get("薪资") or "").strip()
        jd = (r.get("岗位描述") or "").strip()

        s_min, s_max, s_unit = parse_salary(salary_raw)
        city = normalize_city(city_raw)
        skills = basic_skills(jd)
        hr_active = (r.get("HR活跃") or "").strip()

        # 去重键含城市：避免「同公司同岗位同薪资」跨城市被误判为重复
        key = (company.lower(), title.lower(), salary_raw.lower(), city.lower())
        is_dup = key in seen and bool(company) and bool(title)
        if is_dup:
            dup_count += 1
        seen.add(key)

        row = {
            "公司名称": company,
            "岗位名称": title,
            "城市": city_raw,
            "城市_norm": city,
            "薪资": salary_raw,
            "薪资下限": s_min,
            "薪资上限": s_max,
            "薪资单位": s_unit,
            "经验": (r.get("经验") or "").strip(),
            "学历": (r.get("学历") or "").strip(),
            "岗位描述": jd,
            "招聘链接": (r.get("招聘链接") or "").strip(),
            "HR活跃": hr_active,
            "HR活跃天数": active_days(hr_active),
            "技能": skills,
            "重复": is_dup,
            "缺失关键信息": (not company) or (not title),
        }
        cleaned.append(row)

    stats = {
        "total": len(cleaned),
        "duplicates": dup_count,
        "missing_key": sum(1 for r in cleaned if r["缺失关键信息"]),
        "with_salary": sum(1 for r in cleaned if r["薪资下限"] is not None),
        "active_hr": sum(1 for r in cleaned if r["HR活跃天数"] < 999),
        "cities": sorted({r["城市_norm"] for r in cleaned if r["城市_norm"]}),
    }
    return cleaned, stats


def read_csv_text(csv_text):
    f = io.StringIO(csv_text)
    reader = csv.DictReader(f)
    return [dict(row) for row in reader]


# ----------------------------- AI 技能提取 -----------------------------

def ollama_ready():
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/version", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def ai_extract_skills(jd_text, model=MODEL):
    """调用本地 Ollama，从一段 JD 文本提取技能关键词列表。"""
    system = (
        "你是招聘信息解析助手。从用户给出的岗位描述中提取技能关键词，"
        "只输出 JSON，格式：{\"skills\": [\"Python\",\"SQL\",...]}，"
        "不要任何解释文字，不要 markdown 代码块。技能从岗位描述里明确提到的挑，没提到不要编。"
    )
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": jd_text},
        ],
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data.get("message", {}).get("content", "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        obj = json.loads(content)
        skills = obj.get("skills", [])
        if isinstance(skills, list):
            return [str(s).strip() for s in skills if str(s).strip()]
    except Exception:
        pass
    return []


# ----------------------------- 筛选逻辑 -----------------------------

def apply_filter(rows, filters):
    city = (filters.get("city") or "全部").strip()
    min_salary = filters.get("min_salary")
    skills = [s.strip() for s in (filters.get("skills") or []) if s.strip()]
    keyword = (filters.get("keyword") or "").strip()
    exclude_dup = bool(filters.get("exclude_dup"))
    only_complete = bool(filters.get("only_complete"))
    hr_days = filters.get("hr_days")

    try:
        min_salary = float(min_salary) if min_salary not in (None, "", "0") else None
    except (TypeError, ValueError):
        min_salary = None

    try:
        hr_days = int(hr_days) if hr_days not in (None, "", "0") else None
    except (TypeError, ValueError):
        hr_days = None

    out = []
    for r in rows:
        if exclude_dup and r.get("重复"):
            continue
        if only_complete and r.get("缺失关键信息"):
            continue
        if hr_days is not None:
            d = r.get("HR活跃天数")
            if d is None or d > hr_days:
                continue
        if city != "全部" and r.get("城市_norm") != city:
            continue
        if min_salary is not None:
            s_max = r.get("薪资上限")
            s_min = r.get("薪资下限")
            ok = False
            if s_max is not None and s_max >= min_salary:
                ok = True
            elif s_min is not None and s_min >= min_salary:
                ok = True
            if not ok:
                continue
        if skills:
            row_skills = set(r.get("技能") or [])
            # 必须同时包含所有勾选技能（AND）
            if not all(s in row_skills for s in skills):
                continue
        if keyword:
            hay = (r.get("岗位描述") or "") + " " + (r.get("岗位名称") or "")
            if keyword.lower() not in hay.lower():
                continue
        out.append(r)
    return out


# ----------------------------- HTTP 服务 -----------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except Exception:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_file(os.path.join(HERE, "index.html"),
                            "text/html; charset=utf-8")
        elif self.path == "/api/sample":
            try:
                with open(os.path.join(HERE, "sample_raw.csv"),
                          "r", encoding="utf-8-sig") as f:
                    csv_text = f.read()
                self._send_json({"filename": "sample_raw.csv", "csv": csv_text})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}

        if self.path == "/api/clean":
            csv_text = body.get("csv", "")
            try:
                rows = read_csv_text(csv_text)
                cleaned, stats = clean_rows(rows)
                self._send_json({"rows": cleaned, "stats": stats})
            except Exception as e:
                self._send_json({"error": "清洗失败：" + str(e)}, 500)

        elif self.path == "/api/filter":
            rows = body.get("rows", [])
            filters = body.get("filters", {})
            out = apply_filter(rows, filters)
            self._send_json({
                "rows": out,
                "matched": len(out),
                "total": len(rows),
            })

        elif self.path == "/api/extract":
            rows = body.get("rows", [])
            if not ollama_ready():
                self._send_json({"error": "本地大模型(Ollama)未运行，请先启动再试",
                                 "rows": rows}, 200)
                return
            limit = int(body.get("limit", 30))
            done = 0
            for r in rows:
                if done >= limit:
                    break
                jd = r.get("岗位描述") or ""
                if not jd.strip():
                    continue
                try:
                    sk = ai_extract_skills(jd)
                    if sk:
                        r["技能"] = sk
                        done += 1
                except Exception:
                    pass
            self._send_json({"rows": rows, "extracted": done,
                             "ollama": MODEL})

        elif self.path == "/api/fetch":
            # 实时采集：懒加载 fetch_boss，缺失依赖时给友好提示，不影响其余功能
            keyword = (body.get("keyword") or "").strip()
            city = (body.get("city") or "").strip()
            try:
                pages = int(body.get("pages", 3))
            except (TypeError, ValueError):
                pages = 3
            try:
                details = int(body.get("details", 0))
            except (TypeError, ValueError):
                details = 0
            try:
                import fetch_boss
            except ImportError:
                self._send_json({"error": (
                    "实时采集脚本缺失（boss_scraper 目录）。"
                    "请确认项目完整，并双击 start.bat 重新安装依赖。")}, 200)
                return
            try:
                raw = fetch_boss.fetch_jobs(keyword=keyword, city=city,
                                           pages=pages, details=details,
                                           headless=False)
                cleaned, stats = clean_rows(raw)
                self._send_json({"rows": cleaned, "stats": stats,
                                 "fetched": len(raw)})
            except Exception as e:
                self._send_json({"error": "采集失败：" + str(e)}, 200)

        else:
            self.send_error(404)


def main():
    log_boot(f"[{time.strftime('%H:%M:%S')}] starting on 127.0.0.1:{PORT}")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except Exception as e:
        log_boot(f"[{time.strftime('%H:%M:%S')}] bind error: {e}")
        return
    print(f"BOSS 岗位工具已启动： http://localhost:{PORT}")
    print("按 Ctrl+C 停止。")
    log_boot(f"[{time.strftime('%H:%M:%S')}] listening OK")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    log_boot(f"[{time.strftime('%H:%M:%S')}] stopped")


if __name__ == "__main__":
    main()
