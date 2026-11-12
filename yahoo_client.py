# -*- coding: utf-8 -*-
"""
Yahoo Fantasy Sports API 客户端（OAuth 2.0 Authorization Code 流程，手动粘贴 code）

用法（命令行）:
  python yahoo_client.py setup --key <CLIENT_ID> --secret <CLIENT_SECRET>
  python yahoo_client.py authorize
  python yahoo_client.py status
  python yahoo_client.py league   <league_key>            # 联盟基本信息
  python yahoo_client.py settings <league_key>            # 联盟设置（赛制、类别）
  python yahoo_client.py standings <league_key>           # 积分榜
  python yahoo_client.py teams     <league_key>           # 所有球队
  python yahoo_client.py roster    <team_key>             # 某队阵容+球员数据
  python yahoo_client.py players   <league_key> [--start 0] # 联盟球员池

league_key 形如 nba.l.12345；team_key 形如 nba.l.12345.t.1
所有命令加 --raw 可输出 Yahoo 原始 JSON。

前置条件: Yahoo App 的 Redirect URI(s) 必须包含 https://basketball.fantasysports.yahoo.com/
（Yahoo 强制 https 回调；授权后浏览器跳回 Yahoo Fantasy 首页并带上 ?code= 参数，
把地址栏完整 URL 复制出来即可）
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

SKILL_DIR = Path(__file__).resolve().parent.parent
CRED_FILE = SKILL_DIR / ".env"
TOKEN_FILE = SKILL_DIR / "tokens.json"
# Yahoo 强制 https 回调且禁用 yahoo/google 等大站域名；使用 example.com 中转，
# 跳转后页面内容无关紧要，只需从地址栏复制 code 参数
REDIRECT_URI = "https://example.com/"

API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


# ---------------------------------------------------------------- credentials

def save_credentials(consumer_key: str, consumer_secret: str) -> None:
    CRED_FILE.write_text(
        f"YAHOO_CONSUMER_KEY={consumer_key}\nYAHOO_CONSUMER_SECRET={consumer_secret}\n",
        encoding="utf-8",
    )
    print(f"[OK] 凭据已保存到 {CRED_FILE}")


def load_credentials():
    if not CRED_FILE.exists():
        return None, None
    vals = {}
    for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals.get("YAHOO_CONSUMER_KEY"), vals.get("YAHOO_CONSUMER_SECRET")


def _basic_auth() -> str:
    ck, cs = load_credentials()
    if not ck or not cs:
        sys.exit("[X] 缺少 Yahoo App 凭据。先运行: python yahoo_client.py setup --key <KEY> --secret <SECRET>")
    return base64.b64encode(f"{ck}:{cs}".encode()).decode()


# ---------------------------------------------------------------------- token

def save_tokens(payload: dict) -> None:
    payload = dict(payload)
    payload["obtained_at"] = int(time.time())
    TOKEN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_tokens():
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return None


def token_expired(tokens: dict, margin: int = 120) -> bool:
    if not tokens or "access_token" not in tokens:
        return True
    elapsed = time.time() - tokens.get("obtained_at", 0)
    return elapsed >= int(tokens.get("expires_in", 3600)) - margin


def refresh_access_token(tokens: dict) -> dict:
    r = _request(
        TOKEN_URL,
        headers={"Authorization": f"Basic {_basic_auth()}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        method="post",
    )
    if r.status_code != 200:
        sys.exit(f"[X] 刷新 token 失败: HTTP {r.status_code}\n{r.text[:500]}\n请重新运行 authorize")
    new = r.json()
    # Yahoo 可能不返回新的 refresh_token，沿用旧的
    new.setdefault("refresh_token", tokens["refresh_token"])
    save_tokens(new)
    return new


def get_access_token() -> str:
    tokens = load_tokens()
    if tokens and token_expired(tokens):
        tokens = refresh_access_token(tokens)
    if not tokens or "access_token" not in tokens:
        sys.exit("[X] 尚未授权。请先运行: python yahoo_client.py authorize")
    return tokens["access_token"]


def cmd_authorize():
    ck, _ = load_credentials()
    # fspt-r = Fantasy Sports 只读 scope，必须显式申请，否则 token 无 fantasy 权限
    url = (f"{AUTHORIZE_URL}?client_id={ck}&redirect_uri={REDIRECT_URI}"
           f"&response_type=code&scope=fspt-r&language=en-us")
    print("=" * 70)
    print("步骤 1/3: 在浏览器中打开下面的链接并登录你的 Yahoo 账号：")
    print(url)
    print("-" * 70)
    print("步骤 2/3: 授权后浏览器会跳转到 Yahoo Fantasy 页面，地址栏会带上 ?code= 参数")
    print("          把浏览器地址栏里的【完整 URL】复制粘贴到下面：")
    print("-" * 70)
    pasted = input("粘贴完整跳转 URL 或其中的 code 参数: ").strip()
    code = pasted
    if "code=" in pasted:
        try:
            code = parse_qs(urlparse(pasted).query)["code"][0]
        except Exception:
            code = pasted.split("code=")[1].split("&")[0]
    # 步骤 3: 换取 access token
    r = _request(
        TOKEN_URL,
        headers={"Authorization": f"Basic {_basic_auth()}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        method="post",
    )
    if r.status_code != 200:
        sys.exit(f"[X] 换取 access token 失败: HTTP {r.status_code}\n{r.text[:500]}")
    save_tokens(r.json())
    print("=" * 70)
    print(f"[OK] 授权完成，token 已保存到 {TOKEN_FILE}（access token 1 小时，脚本会自动续期）")


def cmd_status():
    ck, cs = load_credentials()
    tokens = load_tokens()
    print(f"App 凭据: {'已配置' if ck and cs else '未配置 (运行 setup)'}")
    if tokens and tokens.get("access_token"):
        left = int(tokens.get("expires_in", 3600)) - int(time.time() - tokens.get("obtained_at", 0))
        print(f"用户授权: 已完成 (access token {'有效' if left > 0 else '已过期，将自动刷新'})")
    else:
        print("用户授权: 未完成 (运行 authorize)")


# ----------------------------------------------------------------- API 调用

def _system_proxy():
    """读取 Windows 系统代理（IE 设置），返回 requests proxies 字典或 None。"""
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
        server, _ = winreg.QueryValueEx(k, "ProxyServer")
        if enable:
            addr = server if server.startswith("http") else f"http://{server}"
            return {"http": addr, "https": addr}
    except Exception:
        pass
    return None


def _request(url, headers=None, params=None, data=None, method="get"):
    """带代理兜底的请求：默认代理（环境变量）若被 Yahoo 地区拦截（403 + HTML），
    自动切换 Windows 系统代理重试。"""
    session = requests.Session()
    sys_proxy = _system_proxy()
    for proxies in (None, sys_proxy):  # None = 用环境变量默认代理
        r = session.request(method, url, headers=headers, params=params,
                            data=data, proxies=proxies, timeout=30)
        # 拦截页特征：403 + text/html（正常 API 错误是 JSON）
        if not (r.status_code == 403 and "text/html" in r.headers.get("Content-Type", "")):
            return r
    return r


def fetch(resource_path: str, params: dict = None) -> dict:
    url = f"{API_BASE}/{resource_path.lstrip('/')}"
    params = dict(params or {})
    params["format"] = "json"
    for attempt in range(2):
        r = _request(url, headers={"Authorization": f"Bearer {get_access_token()}"},
                     params=params)
        if r.status_code == 401 and attempt == 0:
            tokens = load_tokens()
            tokens = refresh_access_token(tokens)  # token 失效 → 刷新后重试
            continue
        break
    if r.status_code != 200:
        sys.exit(f"[X] 请求失败: HTTP {r.status_code}\n{r.text[:800]}")
    return r.json()


def dig(data: dict, *keys):
    """逐层取嵌套值，任一层缺失返回 None。"""
    cur = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def league_content(raw: dict) -> dict:
    """从 league 查询原始 JSON 中提取 fantasy_content.league 节点。"""
    return dig(raw, "fantasy_content", "league") or {}


def listify(node) -> list:
    """Yahoo JSON 中 {0:{...},1:{...},count:N} 或 [...] 两种形态统一为列表。"""
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return [v for k, v in node.items() if k != "count"]
    return []


def extract_team_summary(entry: dict) -> dict:
    """team 节点里 [0]=元数据 [1]=统计，合并提炼常用字段。"""
    out = {}
    for part in entry if isinstance(entry, list) else [entry]:
        if isinstance(part, dict):
            for k, v in part.items():
                if isinstance(v, (str, int, float)):
                    out[k] = v
                elif k == "team_points" and isinstance(v, dict):
                    out["points"] = v.get("total")
                elif k == "team_standings" and isinstance(v, dict):
                    out["rank"] = v.get("rank")
                    out["playoff_seed"] = v.get("playoff_seed")
                elif k == "team_stats" and isinstance(v, dict):
                    stats = v.get("stats", {}).get("stat", [])
                    if isinstance(stats, dict):
                        stats = [stats]
                    for s in stats:
                        if s.get("stat_id") in ("0", 0):  # ROTO 总分
                            out["roto_points"] = s.get("value")
    return out


def extract_player(entry) -> dict:
    """player 节点里 [0]=球员元数据 [1]=stat/selected_position 等。"""
    out = {}
    for part in entry if isinstance(entry, list) else [entry]:
        if isinstance(part, dict):
            for k, v in part.items():
                if isinstance(v, (str, int, float)):
                    out[k] = v
                elif k in ("selected_position", "eligible_positions") and isinstance(v, list):
                    out[k] = [p.get("position") for p in v if isinstance(p, dict)]
                elif k == "player_stats" and isinstance(v, dict):
                    stats = v.get("stats", {}).get("stat", [])
                    if isinstance(stats, dict):
                        stats = [stats]
                    out["stats"] = {
                        s.get("name", s.get("stat_id")): s.get("value") for s in stats
                    }
    return out


# ------------------------------------------------------------------ 命令实现

def cmd_league(key: str, raw: bool):
    data = fetch(f"league/{key}")
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    node = league_content(data)
    meta = node[0] if isinstance(node, list) else node
    flat = {}
    if isinstance(meta, dict):
        for k, v in meta.items():
            if isinstance(v, (str, int, float)):
                flat[k] = v
    print(json.dumps(flat, ensure_ascii=False, indent=2))


def cmd_settings(key: str, raw: bool):
    data = fetch(f"league/{key}/settings")
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    node = league_content(data)
    settings = listify(dig(node, "settings"))
    print(json.dumps(settings, ensure_ascii=False, indent=2))


def cmd_standings(key: str, raw: bool):
    data = fetch(f"league/{key}/standings")
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    node = league_content(data)
    teams = listify(dig(node, "standings", "teams"))
    rows = [extract_team_summary(t) for t in teams]
    rows.sort(key=lambda x: x.get("rank") or 999)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_teams(key: str, raw: bool):
    data = fetch(f"league/{key}/teams")
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    node = league_content(data)
    teams = listify(dig(node, "teams"))
    rows = [extract_team_summary(t) for t in teams]
    rows.sort(key=lambda x: x.get("team_key") or "")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_roster(team_key: str, raw: bool):
    data = fetch(f"team/{team_key}/roster/players/stats")
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    team = dig(data, "fantasy_content", "team") or []
    roster = listify(dig(team, "roster", "players")) if isinstance(team, (list, dict)) else []
    players = [extract_player(p) for p in roster]
    print(json.dumps({"team": extract_team_summary(team) if isinstance(team, list) else {},
                      "players": players}, ensure_ascii=False, indent=2))


def cmd_players(key: str, start: int, raw: bool):
    data = fetch(f"league/{key}/players", params={"start": start, "count": 25})
    if raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    node = league_content(data)
    players = listify(dig(node, "players"))
    rows = [extract_player(p) for p in players]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Yahoo Fantasy API 客户端 (OAuth2)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup")
    s.add_argument("--key", required=True)
    s.add_argument("--secret", required=True)

    sub.add_parser("authorize")
    sub.add_parser("status")

    for name, fn_help in [
        ("league", "联盟基本信息"), ("settings", "联盟设置"),
        ("standings", "积分榜"), ("teams", "所有球队"),
        ("players", "球员池"),
    ]:
        p = sub.add_parser(name, help=fn_help)
        p.add_argument("league_key")
        p.add_argument("--start", type=int, default=0)
        p.add_argument("--raw", action="store_true")

    r = sub.add_parser("roster", help="某队阵容")
    r.add_argument("team_key")
    r.add_argument("--raw", action="store_true")

    args = ap.parse_args()
    raw = getattr(args, "raw", False)

    if args.cmd == "setup":
        save_credentials(args.key, args.secret)
    elif args.cmd == "authorize":
        cmd_authorize()
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "league":
        cmd_league(args.league_key, raw)
    elif args.cmd == "settings":
        cmd_settings(args.league_key, raw)
    elif args.cmd == "standings":
        cmd_standings(args.league_key, raw)
    elif args.cmd == "teams":
        cmd_teams(args.league_key, raw)
    elif args.cmd == "roster":
        cmd_roster(args.team_key, raw)
    elif args.cmd == "players":
        cmd_players(args.league_key, args.start, raw)


if __name__ == "__main__":
    main()
