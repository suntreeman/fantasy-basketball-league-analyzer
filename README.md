# Fantasy Basketball League Analyzer

A personal, **read-only** command-line tool for analyzing Yahoo Fantasy Basketball leagues via the official Yahoo Fantasy Sports API.

> ⚠️ This is a private, non-commercial personal project. No data is redistributed or made publicly available.

## Features

- League info & settings (scoring categories, rosters, format)
- Standings (rank, wins/losses, ROTO points)
- All teams with team keys and managers
- Team rosters with player season statistics
- League player pool browsing (free agents / all players, paginated)

All operations are **read-only** (`fspt-r` scope). The tool never writes to your league.

## Setup

### 1. Yahoo Developer App

1. Create an app at [developer.yahoo.com/apps](https://developer.yahoo.com/apps/)
2. Add a redirect URI: `https://example.com/` (Yahoo requires HTTPS; the redirect page itself is not used — only the `?code=` parameter in the address bar matters)
3. Fantasy Sports API access must be approved by Yahoo ([apply here](https://sports.yahoo.com/developer/access/))

### 2. Credentials & Authorization

```bash
python yahoo_client.py setup --key <CLIENT_ID> --secret <CLIENT_SECRET>
python yahoo_client.py authorize    # one-time browser authorization
python yahoo_client.py status
```

Access tokens auto-refresh (1-hour expiry), so you only authorize once.

### 3. Query Your League

League key format: `nba.l.<league_id>` (e.g. `.../nba/48130` → `nba.l.48130`)

```bash
python yahoo_client.py league    nba.l.48130        # league metadata
python yahoo_client.py settings  nba.l.48130        # scoring categories / format
python yahoo_client.py standings nba.l.48130        # standings
python yahoo_client.py teams     nba.l.48130        # all teams
python yahoo_client.py roster    nba.l.48130.t.1    # team roster + player stats
python yahoo_client.py players   nba.l.48130 --start 0   # player pool (25 per page)
```

Add `--raw` to any command to dump the raw Yahoo JSON response.

## Requirements

- Python 3.10+
- `pip install requests requests-oauthlib`
- A system proxy may be required in regions where Yahoo is blocked (auto-detected on Windows)

## Files

| File | Description |
|------|-------------|
| `yahoo_client.py` | Main CLI client (OAuth2 + API queries) |
| `api_reference.md` | Yahoo Fantasy API quick reference (endpoints, key formats, JSON structure) |

## License

For personal use only.
