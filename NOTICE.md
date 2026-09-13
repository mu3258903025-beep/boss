# 第三方代码声明

## eatmoreduck/boss-zhipin-scraper（MIT）

- 来源：<https://github.com/eatmoreduck/boss-zhipin-scraper>
- 许可：MIT（完整原文见 [`boss_scraper/LICENSE`](boss_scraper/LICENSE)）
- 版权：Copyright (c) 2026 eatmoreduck

本项目把它的采集核心 vendored 在 `boss_scraper/` 目录：

- `boss_scraper/scripts/boss_cdp_raw.py` —— 通过 Chrome DevTools Protocol 连接本地真实 Chrome，
  读取页面自身请求到的搜索接口响应，薪资字段为接口明文（不受前端字体加密影响）
- `boss_scraper/data/city_codes.json` —— 全量城市码表

**本项目的改动**：仅把 profile 目录与结果目录从 `~/.boss-zhipin-scraper/` 改到 D 盘
（`boss_scraper/chrome-profile`、`boss_scraper/job-result`），未修改其采集逻辑。

本项目其余代码（清洗 / 筛选 / 网页 / 采集调用封装）为原创，采用 MIT 许可，
见仓库根目录的 [`LICENSE`](LICENSE)。
