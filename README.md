# 美债 5Y / 10Y / 20Y 收益率监控

固收投资经理用的美债收益率监控页，数据源为美国财政部官方 CMT（Daily Treasury Par Yield Curve Rates）。

- **线上地址**：https://us-treasury-monitor.netlify.app
- **更新计划**：每周一、周三、周五 09:30（北京时间）各一次，由 `.github/workflows/scheduled-update.yml` 定时执行
- **数据源**：U.S. Department of the Treasury — Daily Treasury Par Yield Curve Rates（官方 CSV 视图，未改动）
- **部署方式**：Netlify API 直连部署（沿用原 `deploy_netlify.py` 的增量上传方式）

## 文件

| 文件 | 说明 |
|---|---|
| `index.html` | 监控页（纯静态） |
| `data.js` | 数据层 `window.TREASURY_DATA`，由抓取脚本生成，勿手改 |
| `vendor/chart.umd.min.js` | 图表库（本地引用） |
| `fetch_us_treasury.py` | 抓官方 CSV 生成 `data.js` |
| `deploy_netlify.py` | Netlify API 直连部署脚本（增量上传） |
| `.github/workflows/scheduled-update.yml` | 定时任务：一/三/五 09:30 抓数 → 提交 → 发布 |

## 定时任务需要配置的 Secrets

| Secret | 必填 | 说明 |
|---|---|---|
| `NETLIFY_AUTH_TOKEN` | 是 | Netlify 个人访问令牌；不配置则只更新仓库 `data.js`，不发布线上 |
| `NETLIFY_SITE_ID` | 否 | 站点 ID（形如 `xxxxxxxx-xxxx-...`）；不填则按站点名 `us-treasury-monitor` 查找 |

## 手动跑一次

```bash
python fetch_us_treasury.py      # 只更新本地 data.js
python deploy_netlify.py --site-name us-treasury-monitor
```

凭据：环境变量 `NETLIFY_AUTH_TOKEN`，或同目录 `.netlify-token`（已 gitignore）。

---

本页仅供内部研究参考，不构成投资建议。
