# -*- coding: utf-8 -*-
"""
fetch_boss.py —— BOSS 直聘实时采集（通过「本地真实 Chrome + CDP」）

思路来自开源项目 eatmoreduck/boss-zhipin-scraper (MIT)：
基于 Chrome DevTools Protocol 连接你本地已登录的 Chrome，
读取页面自身请求到的搜索接口响应，薪资字段为接口明文，
再由本项目的清洗 / 筛选环节处理。

用法：
    python fetch_boss.py --login    # 一次性：启动 BOSS 专用 Chrome 并登录
    python fetch_boss.py --check    # 检查环境/登录态
    python fetch_boss.py --keyword Python --city 深圳 --pages 3

合规：仅用你自己的账号、看你本就能看到的公开岗位，个人学习用途，请勿批量抓取或转卖。
"""

import os
import sys
import csv
import glob
import json
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPER = os.path.join(HERE, "boss_scraper", "scripts", "boss_cdp_raw.py")
RESULT_DIR = os.path.join(HERE, "boss_scraper", "job-result")
DATA_DIR = os.path.join(HERE, "data")
LATEST_CSV = os.path.join(DATA_DIR, "latest.csv")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _py():
    return sys.executable or "python"


def _run(args, timeout=None):
    """运行抓取脚本，返回 (code, stdout, stderr)。"""
    if not os.path.exists(SCRAPER):
        raise RuntimeError("找不到采集脚本：" + SCRAPER)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([_py(), SCRAPER] + args,
                       capture_output=True, timeout=timeout, env=env)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def _friendly(text):
    t = (text or "").strip()
    if "请先启动" in t or "--setup-chrome" in t or "CDP" in t:
        return ("BOSS 专用 Chrome 未启动 / 未登录。请先双击 start.bat —— 它会启动专用 Chrome "
                "并引导你登录一次。详情：" + t[-200:])
    if "code: 37" in t or "环境存在异常" in t or "访问频繁" in t:
        return "站点返回了访问限制提示（环境存在异常）。请稍后再试，并降低访问频率。" + t[-200:]
    return "采集失败：" + t[-400:]


def _map_jobs(jobs, det_by_link=None):
    """把 CDP 脚本输出的 job 字典，映射成本项目 clean_rows 认识的字段。

    det_by_link: {job_link: 详情记录}。详情记录里有细粒度 HR 活跃度（如「刚刚活跃」）和完整 JD；
    列表 API 只有粗粒度（在线/空），所以能用详情就用详情。
    """
    det_by_link = det_by_link or {}
    rows = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        det = det_by_link.get(j.get("job_link", ""), {})
        tags = [x.strip() for x in (j.get("tags") or "").split("|") if x.strip()]
        exp = tags[0] if len(tags) > 0 else ""
        edu = tags[1] if len(tags) > 1 else ""
        jd = (det.get("jd") or "").strip()
        desc = jd or " ".join(x for x in (j.get("skills"), j.get("job_labels"),
                                          j.get("welfare")) if x)
        active = (det.get("boss_active_status") or "").strip() or \
                 (j.get("boss_active_status") or "").strip()
        rows.append({
            "公司名称": j.get("boss_name", ""),
            "岗位名称": j.get("title", ""),
            "城市": j.get("location", ""),
            "薪资": j.get("salary", ""),
            "经验": exp,
            "学历": edu,
            "岗位描述": desc,
            "招聘链接": j.get("job_link", ""),
            "HR活跃": active,
        })
    return rows


def check_env():
    code, out, err = _run(["--check"], timeout=120)
    return code == 0, (out or "") + "\n" + (err or "")


def login_once():
    """启动 BOSS 专用 Chrome（CDP），等你在里面登录一次；登录态持久保存。"""
    print("=" * 52)
    print("即将启动 BOSS 专用 Chrome（独立 profile，不会动你平时的 Chrome）。")
    print("请在弹出的浏览器里登录 BOSS 直聘；登录成功后本窗口会自动继续。")
    print("=" * 52)
    code, out, err = _run(["--setup-chrome"])
    print(out or err or "")


def fetch_jobs(keyword="", city="", pages=5, details=0, headless=False,
               timeout=20, wait_verify=180):
    """用 CDP 抓取岗位，返回与 clean_rows 兼容的行。

    details: 抓多少条「职位详情」。详情页才有细粒度 HR 活跃度（刚刚活跃/今日活跃…）和完整 JD；
             但每条要等 10-25 秒，所以**默认 0（不抓详情）**，速度最快。
             想要 HR 活跃度时再设成 10~20（会明显变慢）。
    """
    kw = (keyword or "").strip()
    ct = (city or "").strip()
    os.makedirs(RESULT_DIR, exist_ok=True)
    try:
        n = max(1, min(10, int(pages)))     # 该脚本单次上限 10 页（内建限速）
    except (TypeError, ValueError):
        n = 5
    try:
        nd = max(0, int(details))
    except (TypeError, ValueError):
        nd = 0
    # 注意：该脚本的 --output / --detail-output 必须是**完整 .json 文件路径**
    # （它靠 rsplit(".") 派生 csv），传目录会导致 os.replace(目录) 报 PermissionError
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(RESULT_DIR, "boss_jobs_%s.json" % stamp)
    detail_file = os.path.join(RESULT_DIR, "boss_details_%s.json" % stamp)
    args = ["--keyword", kw or "Python", "--city", ct or "全国",
            "--pages", str(n), "--format", "json", "--output", out_file]
    if nd > 0:
        args += ["--detail", "--max-details", str(nd), "--detail-output", detail_file]
    else:
        args += ["--no-detail"]
    code, out, err = _run(args, timeout=1800)
    text = (out or "") + "\n" + (err or "")
    if code != 0:
        raise RuntimeError(_friendly(text))

    latest = out_file if os.path.exists(out_file) else None
    if not latest:
        files = sorted(glob.glob(os.path.join(RESULT_DIR, "boss_jobs_*.json")),
                       key=os.path.getmtime)
        latest = files[-1] if files else None
    if not latest:
        raise RuntimeError("采集结束但没找到结果文件。输出：" + text[-400:])
    with open(latest, "r", encoding="utf-8") as f:
        payload = json.load(f)
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []

    # 读详情（若有），按 job_link 建索引，用于补 HR活跃度 与 JD
    det_by_link = {}
    if nd > 0 and os.path.exists(detail_file):
        try:
            with open(detail_file, "r", encoding="utf-8") as f:
                dets = json.load(f)
            if isinstance(dets, list):
                for d in dets:
                    if isinstance(d, dict):
                        k = d.get("job_link") or d.get("link") or ""
                        if k:
                            det_by_link[k] = d
        except Exception:
            pass

    rows = _map_jobs(jobs, det_by_link)
    _save_csv(rows, LATEST_CSV)
    return rows


def _save_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cols = ["公司名称", "岗位名称", "城市", "薪资", "经验", "学历", "岗位描述", "招聘链接", "HR活跃"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def main():
    import argparse
    ap = argparse.ArgumentParser(description="BOSS 直聘实时采集（CDP）")
    ap.add_argument("--login", action="store_true", help="启动专用 Chrome 并登录一次")
    ap.add_argument("--check", action="store_true", help="检查环境 / 登录态")
    ap.add_argument("--keyword", default="", help="搜索关键词，如 Python")
    ap.add_argument("--city", default="", help="城市名，如 深圳（留空=全国）")
    ap.add_argument("--pages", type=int, default=5, help="页数（上限 10）")
    args = ap.parse_args()

    if args.check:
        ok, info = check_env()
        print("环境：" + ("OK" if ok else "未就绪"))
        print(info)
        return
    if args.login:
        login_once()
        return

    rows = fetch_jobs(keyword=args.keyword, city=args.city, pages=args.pages)
    print("共采集到 %d 条岗位，已保存到 %s" % (len(rows), LATEST_CSV))


if __name__ == "__main__":
    main()
