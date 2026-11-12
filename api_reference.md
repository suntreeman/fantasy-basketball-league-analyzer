# Yahoo Fantasy Sports API 参考

## 认证

- OAuth 1.0a 三步授权（out-of-band，callback_uri=`oob`）
- Request Token: `https://api.login.yahoo.com/oauth/v2/get_request_token`
- 用户授权: `https://api.login.yahoo.com/oauth/v2/request_auth?oauth_token=...`（页面显示 7 位验证码）
- Access Token: `https://api.login.yahoo.com/oauth/v2/get_token`（携带 oauth_verifier）
- Access token 长期有效，直到用户在 Yahoo 账户设置中撤销授权

## API 基础

- Base: `https://fantasysports.yahooapis.com/fantasy/v2`
- 所有请求需 OAuth1 签名（access token），加参数 `format=json`
- 主要资源路径：
  - `game/nba` — NBA 游戏信息（当前赛季 game_key 如 `nba` 或 `461`）
  - `league/{league_key}` — 联盟元数据
  - `league/{league_key}/settings` — 联盟设置（roster_positions, stat_categories, scoring）
  - `league/{league_key}/standings` — 积分榜
  - `league/{league_key}/teams` — 所有球队
  - `league/{league_key}/players?start=0&count=25` — 球员池（翻页 start 每次 +25）
  - `team/{team_key}` — 球队信息
  - `team/{team_key}/roster/players/stats` — 阵容 + 球员统计（可加 `/stats` 子资源）
  - `player/{player_key}` — 单个球员

## Key 格式

- game key: `nba`（当前赛季）；历史赛季为数字如 `415`
- league key: `{game_key}.l.{league_id}` → `nba.l.48130`
- team key: `{league_key}.t.{team_index}` → `nba.l.48130.t.1`
- player key: `{game_key}.p.{player_id}` → `nba.p.4197`

## JSON 响应结构

统一入口 `fantasy_content`，下接 `league` / `team` / `players` 节点。
集合节点（teams/players/roster）通常是 `{0: {...}, 1: {...}, count: N}`，
单个节点（league/team/player）通常是 `[元数据部分, 内容部分]` 两段数组。

## 常见错误

- 401 — token 失效或凭据错误 → 重新 authorize
- 403/404 — 私有联盟无权限，或 key 不存在 → 确认授权账号在盟内、key 正确
- 空数据 — 赛季未开始或字段缺失，用 `--raw` 检查原始结构
