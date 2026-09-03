# Doubao-daily-brief · 盖世小鸡行业资讯自动简报

基于 GitHub Actions 的定时资讯抓取与飞书推送，覆盖：

- **盖世小鸡官方**：官网 xiaoji.com 新品/联名/代言动态（一手）
- **国外游戏媒体**：IGN、IGN中国、Eurogamer、PC Gamer、RockPaperShotgun、The Verge
- **国外硬件**：Tom's Hardware
- **国内科技/数码**：IT之家、游民星空·硬件、3DM新闻

## 工作方式

- GitHub Actions 每天 **北京时间 09:30 / 21:30** 自动运行 `fetch_gamesir.py`
- 脚本抓取 RSS + HTML → 相关性四级分类（核心/行业/硬件/竞品）→ 24h 时间窗 + 去重
- 生成简报 → POST 到飞书群自定义机器人 webhook
- `seen.json` 用于去重，每次运行后自动回写仓库

## 配置

1. 在飞书群添加「自定义机器人」，复制 webhook 地址
2. 在仓库 Settings → Secrets and variables → Actions 中添加 Secret：
   - 名称：`FEISHU_WEBHOOK`
   - 值：你的飞书 webhook 地址
3. 推送代码后，可在 Actions 页手动 `Run workflow` 测试一次

## 本地手动运行（可选）

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
python fetch_gamesir.py 24
```
