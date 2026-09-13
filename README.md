# BOSS 直聘岗位采集 · 清洗 · 筛选项目

一个**本地运行**的岗位数据处理工具，把杂乱的 BOSS 直聘岗位数据整理成可直接分析的结构化表格，并按城市 / 薪资 / 技能要求筛选目标岗位。核心清洗 / 筛选**零第三方依赖**；可选启用「实时拉取」能力（用你自己的 BOSS 账号一键拉取当下岗位，基于 CDP 连接本地已登录 Chrome，无需安装浏览器驱动，依赖 `websocket-client` + `requests`，由 `start.bat` 自动安装）。

> 项目定位：个人学习用途。处理**你提供**的公开岗位数据，也支持**用你自己的 BOSS 账号一键拉取公开岗位**；不抓取任何隐私信息，严格遵守合规要求。

---

## 功能

1. **加载数据**：内置示例，也支持上传你自己的岗位 CSV（列：公司名称 / 岗位名称 / 城市 / 薪资 / 经验 / 学历 / 岗位描述 / 招聘链接）。
2. **数据清洗**（脏数据处理，项目重点）：
   - 薪资归一：把 `8-12K`、`15-20K·13薪`、`150-200元/天`、`面议` 等解析成「元/月」的上下限
   - 城市归一：`广州·天河区` → `广州`
   - 去重：按「公司 + 岗位 + 薪资」剔除重复记录
   - 空值 / 缺失关键信息标记
   - 正则提取岗位技能关键词（Python / SQL / 爬虫 / pandas …）
3. **筛选**：按城市、最低月薪、技能要求（可多选，需同时包含）、关键词、**HR 活跃度**组合过滤。
   - HR 活跃度：只保留「近期活跃 / 回复」的岗位（今日 / 3日内 / 本周 / 本月），避开长期不回应的 HR，避免白投。
4. **AI 技能提取**：一键调用**本地大模型**（Ollama + qwen3.5:9b）从岗位描述里语义提取技能要求，不依赖固定关键词，数据不出本机。
5. **导出**：一键下载清洗后的 `boss_cleaned.csv`。

## 技术栈

- Python 3（仅标准库：`http.server` / `csv` / `re` / `json` / `urllib`），**无需 pip 安装任何包**
- 前端：原生 HTML + JavaScript，无外部 CDN，离线可用
- AI 提取：本地 Ollama（`qwen3.5:9b`），复用本机已部署的大模型
- 实时拉取（可选）：基于 **Chrome DevTools Protocol (CDP)** 的浏览器自动化采集 —— 连接你本地已登录的 Chrome，读取页面自身请求到的搜索接口响应（薪资字段为接口明文），无需安装浏览器驱动（依赖 `websocket-client` + `requests`，由 `start.bat` 自动安装）

> 对应岗位 JD 要求的：Python、`requests`/`BeautifulSoup`、pandas（清洗逻辑等价）、正则、`SQLite`/`SQL`（可选）、`matplotlib` 可视化（可选）能力。

## 运行方式

### 方式一：双击即用（推荐）

双击 `D:\BossJob\start.bat`（**唯一入口，已整合全部步骤**）：
- 首次自动安装采集依赖（`websocket-client`、`requests`）
- 首次启动一个「BOSS 专用 Chrome」并引导你登录一次（登录态持久保存）
- 自动确保本地大模型（Ollama）已启动
- 启动网页工具并自动打开浏览器 `http://localhost:8090`

> 旧名字 `launch.bat` / `setup_fetch.bat` / `login_boss.bat` 仍可用，它们已转发到 `start.bat`。

### 方式二：命令行

```bat
:: 先确保 Ollama 在跑（AI 提取功能需要）
D:\Ollama\App\ollama.exe serve

:: 另开一个窗口启动工具
python D:\BossJob\boss_job.py
```

然后浏览器打开 `http://localhost:8090`。

## 实时采集（可选）

不想自己准备 CSV？可以一键从 BOSS 直聘拉取**你账号当下能看到的公开岗位**，直接在网页里筛选。

### 一次性准备
直接双击 `start.bat` 即可：它会自动装依赖，并在首次运行时启动一个「BOSS 专用 Chrome」（独立 profile，不影响你平时的浏览器）让你登录一次；登录态持久保存，之后不用再登。

### 日常使用
在网页顶部「🔄 实时拉取 BOSS 岗位」面板填好 **关键词 / 城市 / 翻页次数**，点「拉取并筛选」：
- 工具用你的登录态抓取，抓到的卡片自动清洗并载入表格
- 之后照常使用城市 / 薪资 / 技能 等筛选条件即可

> 说明：「实时」= 你点击时拉取的**当下**数据，不是后台自动推送。抓取时请保持「BOSS 专用 Chrome」开着。
> 原理：不额外启动受控浏览器，而是通过 CDP 连接你已登录的 Chrome，读取页面自身请求到的搜索接口响应，薪资字段为接口明文。

### 命令行也可用
```bat
python D:\BossJob\fetch_boss.py --keyword Python --city 深圳 --pages 3
python D:\BossJob\fetch_boss.py --login     :: 仅首次登录用
python D:\BossJob\fetch_boss.py --check     :: 检查环境/登录态
```
结果会保存到 `data/latest.csv`。抓取核心是 vendored 的 `boss_scraper/scripts/boss_cdp_raw.py`（开源 `eatmoreduck/boss-zhipin-scraper`，MIT）。

### 如果 BOSS 拦截自动采集（更稳的替代：书签导出）
站点对自动化访问较为敏感，可能返回「安全验证」页。此时可改用**书签导出**（在当前页面内完成，不额外发起请求）：

1. 双击打开 `BOSS导出书签.html`
2. 按 `Ctrl + Shift + B` 显示书签栏，把页面里的「📥 BOSS岗位导出」按钮**拖到书签栏**
3. 在**你自己的 Chrome** 里正常搜 BOSS 岗位，列表出来后点一下书签 → 自动下载一个 CSV
4. 回到工具页 `http://localhost:8090` →「上传 CSV」导入 → 清洗 + 筛选

原理：在你自己的浏览器里读取当前页面的岗位卡片（无自动化），导出成工具能识别的 CSV。

## 合规声明

- 仅采集 / 处理**公开可访问**的岗位信息，不抓取手机号、微信、简历等任何个人隐私。
- 本项目为个人学习研究，**非商业用途**。
- 若用于实际采集，请遵守目标网站 `robots.txt` 与相关法律法规，控制请求频率。
- 本工具**不破解验证码、不突破任何访问控制**，仅以已登录的真实浏览器读取公开岗位，并内置限速（每页 12-22 秒、单次最多 10 页）。

## 开源许可与第三方代码

- 本项目自研部分（清洗 / 筛选 / 网页 / 采集封装）采用 **MIT**，见 [`LICENSE`](LICENSE)。
- `boss_scraper/` 是 vendored 的第三方采集核心（MIT），署名与许可原文见
  [`NOTICE.md`](NOTICE.md) 与 [`boss_scraper/LICENSE`](boss_scraper/LICENSE)。
- **提交前务必确认**：`.gitignore` 已排除 `chrome-profile/`（登录态）、`job-result/`（抓取结果）、
  `data/_debug.*` 等含个人隐私的产物，请勿上传任何抓取数据或 Cookie。

## 简历项目描述（可直接复制）

> BOSS 直聘公开岗位数据采集与筛选项目：使用 Python 完成公开招聘信息的结构化清洗，将薪资、城市等杂乱文本解析为统一字段，利用去重与空值处理整理为可用数据表；编写筛选逻辑按城市、薪资门槛与技能要求过滤目标岗位，并调用本地大模型（Ollama + qwen3.5:9b）从岗位描述中语义提取技能关键词。项目纯标准库实现、零第三方依赖，严格遵守合规要求，仅处理公开非隐私数据。

## 目录结构

```
D:\BossJob\
├─ start.bat           # 【唯一入口】一键全流程：装依赖 → 登录 → 起服务 → 开网页
├─ boss_job.py         # 后端：清洗 / 筛选 / AI 提取 / 实时拉取 API
├─ index.html          # 网页界面（含实时拉取面板 + HR活跃筛选）
├─ fetch_boss.py       # 实时采集入口（调用下面的 CDP 脚本，并转成本项目字段）
├─ boss_scraper\       # vendored：eatmoreduck/boss-zhipin-scraper (MIT)
│  ├─ scripts\boss_cdp_raw.py   # CDP 抓取核心
│  ├─ data\city_codes.json      # 全量城市码表
│  ├─ chrome-profile\           # BOSS 专用 Chrome 的登录态（首次登录后生成）
│  └─ job-result\               # 原始抓取结果（JSON）
├─ BOSS导出书签.html          # 备用：在你自己的浏览器里一键导出（页面内完成，无额外请求）
├─ launch.bat / setup_fetch.bat / login_boss.bat   # 旧入口，已转发到 start.bat
├─ sample_raw.csv      # 示例脏数据
├─ data\latest.csv     # 实时拉取结果缓存（本项目字段）
└─ README.md
```
