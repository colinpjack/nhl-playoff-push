#!/usr/bin/env python3
"""Fetch NHL playoff-race data and write the league board plus one file per team."""

from __future__ import annotations

import hashlib
import json
import random
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
USER_AGENT = "NHLPlayoffPush/1.0 (+github-pages refresh)"
ROOT = Path(__file__).resolve().parents[1]
LEAGUE_PATH = ROOT / "data" / "league.json"
TEAMS_DIR = ROOT / "data" / "teams"
FINAL_STATES = {"OFF", "FINAL", "OVER"}
LIVE_STATES = {"LIVE", "CRIT"}
CLINCHED = {"x", "y", "z", "p"}
OT_RATE = 0.23
HOME_BUMP = 0.04
SIMS = 2500

THEMES = {
    "ANA": ("#F47A38", "#B9975B", "#111111", "#f6c7a8"),
    "BOS": ("#FFB81C", "#111111", "#111111", "#ffe7a3"),
    "BUF": ("#003087", "#FFB81C", "#002654", "#f3d48a"),
    "CAR": ("#CC0000", "#111111", "#1a1a1a", "#d0d0d0"),
    "CBJ": ("#002654", "#CE1126", "#041E42", "#A4C8E1"),
    "CGY": ("#C8102E", "#F1BE48", "#111111", "#F1BE48"),
    "CHI": ("#CF0A2C", "#FF671B", "#0B1F3A", "#e7e7e7"),
    "COL": ("#6F263D", "#236192", "#111111", "#A2AAAD"),
    "DAL": ("#006847", "#8F8F8C", "#111111", "#c5c5c2"),
    "DET": ("#CE1126", "#FFFFFF", "#111111", "#f0d9a0"),
    "EDM": ("#041E42", "#FF4C00", "#111111", "#FF4C00"),
    "FLA": ("#041E42", "#C8102E", "#B9975B", "#C8102E"),
    "LAK": ("#111111", "#A2AAAD", "#572A84", "#d5d5d5"),
    "MIN": ("#154734", "#A6192E", "#EAAA00", "#DDCBA4"),
    "MTL": ("#AF1E2D", "#192168", "#111111", "#f2f2f2"),
    "NJD": ("#CE1126", "#111111", "#111111", "#f2f2f2"),
    "NSH": ("#FFB81C", "#041E42", "#111111", "#fff4cc"),
    "NYI": ("#00539B", "#F47D30", "#111111", "#f6c7a8"),
    "NYR": ("#0038A8", "#CE1126", "#111111", "#f2f2f2"),
    "OTT": ("#C52032", "#C2912C", "#111111", "#f3e2b0"),
    "PHI": ("#F74902", "#111111", "#111111", "#f2f2f2"),
    "PIT": ("#111111", "#FCB514", "#CFC493", "#ffe7a3"),
    "SEA": ("#001628", "#99D9D9", "#355464", "#d7f3f3"),
    "SJS": ("#006D75", "#EA7200", "#111111", "#f6c7a8"),
    "STL": ("#002F87", "#FCB514", "#041E42", "#ffe7a3"),
    "TBL": ("#002868", "#FFFFFF", "#111111", "#f2f2f2"),
    "TOR": ("#00205B", "#FFFFFF", "#111111", "#f2f2f2"),
    "UTA": ("#6CACE4", "#010101", "#010101", "#d7e8f6"),
    "VAN": ("#00205B", "#00843D", "#041C2C", "#b7e0c8"),
    "VGK": ("#B4975A", "#333F42", "#111111", "#e6d7b0"),
    "WPG": ("#041E42", "#AC162C", "#004C97", "#f2f2f2"),
    "WSH": ("#041E42", "#C8102E", "#111111", "#f2c9ce"),
}

_PREFER_CURL = False


def now_local() -> datetime:
    return datetime.now(TZ)


def target_season_id(now: datetime) -> int:
    start = now.year if now.month >= 7 else now.year - 1
    return int(f"{start}{start + 1}")


def previous_season_id(season: int) -> int:
    start = int(str(season)[:4]) - 1
    return int(f"{start}{start + 1}")


def season_label(season: int) -> str:
    text = str(season)
    return f"{text[:4]}–{text[6:]}"


def loc(value) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or next(iter(value.values()), "") or "")
    return "" if value is None else str(value)


def fetch_json(url: str, retries: int = 3) -> dict:
    global _PREFER_CURL
    last_err: Exception | None = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if not _PREFER_CURL:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                    return json.load(resp)
            except Exception as err:
                last_err = err
                time.sleep(0.35 * (attempt + 1))
        _PREFER_CURL = True
    for attempt in range(retries):
        try:
            completed = subprocess.run(
                ["curl", "-fsSL", "-A", USER_AGENT, "--max-time", "45", url],
                check=True,
                capture_output=True,
                text=True,
                timeout=50,
            )
            return json.loads(completed.stdout)
        except Exception as err:
            last_err = err
            time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}") from last_err


def try_fetch(url: str) -> dict | None:
    try:
        return fetch_json(url)
    except Exception as err:
        print(f"  skipped {url}: {err}", flush=True)
        return None


def wlt(wins: int, losses: int, otl: int) -> str:
    return f"{wins}-{losses}-{otl}"


def streak_label(code: str | None, count: int | None) -> str:
    if not code or not count:
        return "—"
    return f"{code}{int(count)}"


def full_name(team: dict) -> str:
    place = (team.get("place") or "").strip()
    common = (team.get("common") or team.get("name") or team.get("abbr") or "").strip()
    if not place:
        return common
    if common and common in place:
        return place
    if place in common:
        return common
    return f"{place} {common}"


def conf_short(team: dict) -> str:
    abbrev = team.get("conferenceAbbrev") or ""
    name = team.get("conference") or ""
    if abbrev == "E" or "East" in name:
        return "East"
    if abbrev == "W" or "West" in name:
        return "West"
    return name or abbrev or "Conference"


def blank_counts() -> dict:
    return {
        "gp": 0, "wins": 0, "losses": 0, "otl": 0, "points": 0, "rw": 0, "row": 0,
        "gf": 0, "ga": 0, "diff": 0,
        "homeWins": 0, "homeLosses": 0, "homeOtl": 0, "homePoints": 0,
        "roadWins": 0, "roadLosses": 0, "roadOtl": 0, "roadPoints": 0,
        "l10Wins": 0, "l10Losses": 0, "l10Otl": 0, "l10Points": None, "l10gp": 0,
        "streak": "—", "clinch": "", "pointPct": None, "record": "0-0-0",
        "home": "0-0-0", "road": "0-0-0", "l10": "—",
    }


def finish_rates(team: dict, season_games: int) -> None:
    team["diff"] = int(team["gf"]) - int(team["ga"])
    team["record"] = wlt(team["wins"], team["losses"], team["otl"])
    team["home"] = wlt(team["homeWins"], team["homeLosses"], team["homeOtl"])
    team["road"] = wlt(team["roadWins"], team["roadLosses"], team["roadOtl"])
    if team["l10gp"]:
        team["l10"] = wlt(team["l10Wins"], team["l10Losses"], team["l10Otl"])
    else:
        team["l10"] = "—"
        team["l10Points"] = None
    gp = int(team["gp"])
    team["pointPct"] = round(team["points"] / (2 * gp), 3) if gp else None
    scheduled = int(team.get("seasonGames") or season_games or 0)
    team["pace"] = round(team["points"] / gp * scheduled) if gp and scheduled else None
    team["maxPoints"] = int(team["points"]) + 2 * int(team.get("gr") or 0)
    team["xpts"] = expected_points(team["gf"], team["ga"], gp)
    team["otWins"] = max(0, int(team["row"]) - int(team["rw"]))
    team["soWins"] = max(0, int(team["wins"]) - int(team["row"]))


def expected_points(gf: int, ga: int, gp: int) -> float | None:
    if gp <= 0 or (gf <= 0 and ga <= 0):
        return None
    exp = 2.05
    gf_e = max(gf, 0) ** exp
    ga_e = max(ga, 0) ** exp
    if gf_e + ga_e == 0:
        return None
    return round((gf_e / (gf_e + ga_e)) * 2 * gp, 1)


def meta_from_row(row: dict) -> dict:
    return {
        "abbr": loc(row.get("teamAbbrev")),
        "name": loc(row.get("teamName")),
        "common": loc(row.get("teamCommonName")),
        "place": loc(row.get("placeName")),
        "logo": row.get("teamLogo") or "",
        "conference": row.get("conferenceName") or "",
        "conferenceAbbrev": row.get("conferenceAbbrev") or "",
        "division": row.get("divisionName") or "",
        "divisionAbbrev": row.get("divisionAbbrev") or "",
    }


def apply_official_row(team: dict, row: dict) -> None:
    team.update(blank_counts())
    team.update({
        "gp": int(row.get("gamesPlayed") or 0),
        "wins": int(row.get("wins") or 0),
        "losses": int(row.get("losses") or 0),
        "otl": int(row.get("otLosses") or 0),
        "points": int(row.get("points") or 0),
        "rw": int(row.get("regulationWins") or 0),
        "row": int(row.get("regulationPlusOtWins") or 0),
        "gf": int(row.get("goalFor") or 0),
        "ga": int(row.get("goalAgainst") or 0),
        "diff": int(row.get("goalDifferential") or 0),
        "homeWins": int(row.get("homeWins") or 0),
        "homeLosses": int(row.get("homeLosses") or 0),
        "homeOtl": int(row.get("homeOtLosses") or 0),
        "homePoints": int(row.get("homePoints") or 0),
        "roadWins": int(row.get("roadWins") or 0),
        "roadLosses": int(row.get("roadLosses") or 0),
        "roadOtl": int(row.get("roadOtLosses") or 0),
        "roadPoints": int(row.get("roadPoints") or 0),
        "l10Wins": int(row.get("l10Wins") or 0),
        "l10Losses": int(row.get("l10Losses") or 0),
        "l10Otl": int(row.get("l10OtLosses") or 0),
        "l10Points": int(row.get("l10Points") or 0),
        "l10gp": int(row.get("l10GamesPlayed") or 0),
        "streak": streak_label(row.get("streakCode"), row.get("streakCount")),
        "clinch": (row.get("clinchIndicator") or "") or "",
    })
    if not team["l10gp"]:
        team["l10Points"] = None


def teams_from_rows(rows: list[dict], season_games: int) -> list[dict]:
    teams = []
    for row in rows:
        team = meta_from_row(row)
        if not team["abbr"]:
            continue
        apply_official_row(team, row)
        team["gr"] = max(0, season_games - team["gp"]) if season_games else 0
        team["seasonGames"] = season_games
        finish_rates(team, season_games)
        teams.append(team)
    return teams


def zero_teams(templates: list[dict], season_games: int) -> list[dict]:
    teams = []
    for src in templates:
        team = {key: src[key] for key in (
            "abbr", "name", "common", "place", "logo", "conference",
            "conferenceAbbrev", "division", "divisionAbbrev",
        )}
        team.update(blank_counts())
        team["gr"] = season_games
        team["seasonGames"] = season_games
        team["maxPoints"] = 2 * season_games
        team["otWins"] = 0
        team["soWins"] = 0
        team["xpts"] = None
        team["pace"] = None
        teams.append(team)
    return teams


def broadcast_names(raw: dict) -> str:
    names = []
    for item in raw.get("tvBroadcasts") or []:
        network = item.get("network")
        if isinstance(network, dict):
            network = loc(network)
        text = str(network or "").strip()
        if text and text not in names:
            names.append(text)
    return ", ".join(names[:3])


def parse_game(raw: dict) -> dict:
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}
    outcome = raw.get("gameOutcome") or {}
    period = outcome.get("lastPeriodType") or (raw.get("periodDescriptor") or {}).get("periodType") or "REG"
    return {
        "id": raw.get("id"),
        "gameType": raw.get("gameType"),
        "date": raw.get("gameDate"),
        "start": raw.get("startTimeUTC"),
        "state": raw.get("gameState") or "",
        "venue": loc(raw.get("venue")),
        "broadcast": broadcast_names(raw),
        "home": home.get("abbrev"),
        "away": away.get("abbrev"),
        "homeScore": home.get("score"),
        "awayScore": away.get("score"),
        "periodType": period,
        "ot": period in {"OT", "SO"},
        "homeLogo": home.get("logo") or "",
        "awayLogo": away.get("logo") or "",
    }


def collect_games(schedules: dict[str, dict]) -> list[dict]:
    found: dict[int, dict] = {}
    for payload in schedules.values():
        for raw in payload.get("games") or []:
            game = parse_game(raw)
            if game["id"] is not None and game["home"] and game["away"]:
                found[int(game["id"])] = game
    return sorted(found.values(), key=lambda game: (game["date"] or "", game["id"] or 0))


def result_for(abbr: str, game: dict) -> str | None:
    if game.get("homeScore") is None or game.get("awayScore") is None:
        return None
    us = game["homeScore"] if game["home"] == abbr else game["awayScore"]
    them = game["awayScore"] if game["home"] == abbr else game["homeScore"]
    if us > them:
        return "W"
    if game["ot"]:
        return "OTL"
    return "L"


def points_for(result: str) -> int:
    if result == "W":
        return 2
    if result == "OTL":
        return 1
    return 0


def apply_results(teams: list[dict], games: list[dict], season_games: int) -> None:
    by_abbr = {team["abbr"]: team for team in teams}
    for team in teams:
        clinch = team.get("clinch") or ""
        team.update(blank_counts())
        team["clinch"] = clinch
        team["seasonGames"] = season_games
    finals = [
        game for game in games
        if game["gameType"] == 2 and game["state"] in FINAL_STATES and game["homeScore"] is not None
    ]
    for game in finals:
        home = by_abbr.get(game["home"])
        away = by_abbr.get(game["away"])
        if not home or not away or game["homeScore"] == game["awayScore"]:
            continue
        if game["homeScore"] > game["awayScore"]:
            winner, loser = home, away
            wscore, lscore = game["homeScore"], game["awayScore"]
            winner_home = True
        else:
            winner, loser = away, home
            wscore, lscore = game["awayScore"], game["homeScore"]
            winner_home = False
        winner["wins"] += 1
        winner["points"] += 2
        winner["gf"] += wscore
        winner["ga"] += lscore
        loser["gf"] += lscore
        loser["ga"] += wscore
        winner["gp"] += 1
        loser["gp"] += 1
        if winner_home:
            winner["homeWins"] += 1
            winner["homePoints"] += 2
        else:
            winner["roadWins"] += 1
            winner["roadPoints"] += 2
        if game["ot"]:
            loser["otl"] += 1
            loser["points"] += 1
            winner["row"] += 1
            if winner_home:
                loser["roadOtl"] += 1
                loser["roadPoints"] += 1
            else:
                loser["homeOtl"] += 1
                loser["homePoints"] += 1
        else:
            loser["losses"] += 1
            winner["rw"] += 1
            winner["row"] += 1
            if winner_home:
                loser["roadLosses"] += 1
            else:
                loser["homeLosses"] += 1
    for team in teams:
        theirs = [game for game in finals if team["abbr"] in (game["home"], game["away"])]
        theirs.sort(key=lambda game: (game["date"] or "", game["id"] or 0))
        last = theirs[-10:]
        if last:
            results = [result_for(team["abbr"], game) or "L" for game in last]
            team["l10Wins"] = results.count("W")
            team["l10Losses"] = results.count("L")
            team["l10Otl"] = results.count("OTL")
            team["l10gp"] = len(results)
            team["l10Points"] = sum(points_for(item) for item in results)
            streak_code = {"W": "W", "L": "L", "OTL": "OT"}[results[-1]]
            count = 1
            for item in reversed(results[:-1]):
                if {"W": "W", "L": "L", "OTL": "OT"}[item] != streak_code:
                    break
                count += 1
            team["streak"] = f"{streak_code}{count}"
        team["gr"] = sum(
            1 for game in games
            if game["gameType"] == 2 and game["state"] not in FINAL_STATES and team["abbr"] in (game["home"], game["away"])
        )
        finish_rates(team, season_games)


def tie_key(team: dict) -> tuple:
    return (
        -int(team.get("points") or 0),
        -int(team.get("rw") or 0),
        -int(team.get("row") or 0),
        -int(team.get("wins") or 0),
        -int(team.get("diff") or 0),
        team.get("abbr") or "",
    )


def division_ranks(teams: list[dict]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    groups: dict[tuple, list] = {}
    for team in teams:
        groups.setdefault((team.get("conferenceAbbrev"), team.get("divisionAbbrev")), []).append(team)
    for members in groups.values():
        for index, team in enumerate(sorted(members, key=tie_key), start=1):
            ranks[team["abbr"]] = index
    return ranks


def official_seeds(teams: list[dict]) -> dict[str, int]:
    seeds: dict[str, int] = {}
    by_conf: dict[str, list] = {}
    for team in teams:
        by_conf.setdefault(team.get("conferenceAbbrev") or "", []).append(team)
    for members in by_conf.values():
        by_div: dict[str, list] = {}
        for team in members:
            by_div.setdefault(team.get("divisionAbbrev") or "", []).append(team)
        winners = []
        autos = []
        for group in by_div.values():
            ranked = sorted(group, key=tie_key)
            if ranked:
                winners.append(ranked[0])
            autos.extend(ranked[1:3])
        winners.sort(key=tie_key)
        autos.sort(key=tie_key)
        inside = {team["abbr"] for team in winners + autos}
        wild = sorted((team for team in members if team["abbr"] not in inside), key=tie_key)
        wild_in = wild[:2]
        rest = wild[2:]
        for index, team in enumerate(winners + autos + wild_in + rest, start=1):
            seeds[team["abbr"]] = index
    return seeds


def path_label(team: dict, ranks: dict[str, int], seed: int) -> str:
    rank = ranks.get(team["abbr"]) or 99
    if rank <= 3:
        return f"{team.get('division') or 'Division'} {rank}"
    if seed <= 8:
        return "Wild card"
    return "Out"


def points_back(team: dict, cut: dict) -> str:
    delta = int(cut["points"]) - int(team["points"])
    if delta == 0:
        return "—"
    if delta < 0:
        return f"+{abs(delta)}"
    return str(delta)


def gap_text(ahead: bool, points: int) -> str:
    if ahead:
        return "In" if points <= 0 else f"{points} up"
    return "0" if points == 0 else str(points)


def max_points(team: dict) -> int:
    return int(team["points"]) + 2 * int(team.get("gr") or 0)


def clinch_points(team: dict, rivals: list[dict], can_finish_ahead: int) -> int | None:
    if not rivals:
        return 0
    maxima = sorted(max_points(rival) for rival in rivals)
    index = len(maxima) - (can_finish_ahead + 1)
    if index < 0:
        return 0
    return max(0, maxima[index] + 1 - int(team["points"]))


def eliminated_now(team: dict, teams: list[dict]) -> bool:
    if (team.get("clinch") or "") in CLINCHED:
        return False
    if team.get("clinch") == "e" and int(team.get("gr") or 0) == 0:
        return True
    cap = max_points(team)
    conf = [
        other for other in teams
        if other.get("conferenceAbbrev") == team.get("conferenceAbbrev") and other["abbr"] != team["abbr"]
    ]
    div = [other for other in conf if other.get("divisionAbbrev") == team.get("divisionAbbrev")]
    others = [other for other in conf if other.get("divisionAbbrev") != team.get("divisionAbbrev")]
    div_ahead = sum(1 for other in div if other["points"] > cap)
    other_ahead = sum(1 for other in others if other["points"] > cap)
    division_dead = div_ahead >= 3
    wild_blockers = max(0, other_ahead - 3) + max(0, div_ahead - 3)
    return division_dead and wild_blockers >= 2


def magic_payload(team: dict, teams: list[dict], season_over: bool, in_field: bool) -> dict:
    nick = team.get("common") or team["abbr"]
    short = conf_short(team)
    if (team.get("clinch") or "") in CLINCHED or (season_over and in_field):
        return {
            "kind": "clinched", "value": "IN", "label": "Playoff berth clinched",
            "sub": f"{short}ern Conference" if short in {"East", "West"} else short,
            "note": f"The {nick} are in. The remaining games are about seeding.",
        }
    conf = [other for other in teams if other.get("conferenceAbbrev") == team.get("conferenceAbbrev") and other["abbr"] != team["abbr"]]
    div = [other for other in conf if other.get("divisionAbbrev") == team.get("divisionAbbrev")]
    division_need = clinch_points(team, div, 2)
    conference_need = clinch_points(team, conf, 7)
    options = [value for value in (division_need, conference_need) if value is not None]
    division_name = team.get("division") or "division"
    if not options:
        return {
            "kind": "pending", "value": "—", "label": "Magic number to clinch",
            "sub": "Points still to bank",
            "note": f"A berth is a top-three {division_name} finish or one of the two wild cards.",
        }
    needed = min(options)
    reachable = 2 * int(team.get("gr") or 0)
    if eliminated_now(team, teams):
        return {
            "kind": "eliminated", "value": "OUT", "label": "Mathematically eliminated",
            "sub": "No path back",
            "note": f"The {nick} cannot reach a top-three finish or a wild card.",
        }
    if needed == 0:
        return {
            "kind": "clinched", "value": "IN", "label": "Playoff berth clinched",
            "sub": short,
            "note": f"No remaining result can push the {nick} out.",
        }
    if needed > reachable:
        return {
            "kind": "pending", "value": "—", "label": "Magic number to clinch",
            "sub": "Nobody has dropped enough points",
            "note": "Every contender can still finish level with a club that wins out. The clinch number appears once rivals are capped.",
        }
    path = f"{division_name} top three" if division_need == needed else "a wild card"
    other = conference_need if division_need == needed else division_need
    note = (
        f"{needed} more points guarantees {path}, no matter how the rest of the {short} finishes. "
        "A win is worth 2. An overtime loss still hands the other team a point."
    )
    if other is not None and other != needed:
        note += f" The other route needs {other}."
    return {
        "kind": "clinch", "value": str(needed), "label": "Magic number to clinch",
        "sub": f"Points to lock {path}", "note": note,
    }


def strength_of(team: dict, prior: dict | None) -> float:
    prior_pct = None if not prior else prior.get("pointPct")
    if prior_pct is None and prior and prior.get("gp"):
        prior_pct = prior["points"] / (2 * prior["gp"])
    base = 0.5 if prior_pct is None else (0.7 * float(prior_pct) + 0.3 * 0.5)
    gp = int(team.get("gp") or 0)
    if gp <= 0 or team.get("pointPct") is None:
        return base
    weight = min(gp, 30) / 30
    return weight * float(team["pointPct"]) + (1 - weight) * base


def home_win_prob(home_strength: float, away_strength: float) -> float:
    sh = min(0.85, max(0.15, home_strength))
    sa = min(0.85, max(0.15, away_strength))
    denom = sh + sa - 2 * sh * sa
    prob = ((sh - sh * sa) / denom) if denom else 0.5
    return min(0.82, max(0.18, prob + HOME_BUMP))


def simulate_all(teams: list[dict], games: list[dict], strength: dict[str, float]) -> dict[str, tuple[int, int]]:
    by_abbr = {team["abbr"]: team for team in teams}
    pending = [
        game for game in games
        if game["gameType"] == 2 and game["state"] not in FINAL_STATES
        and game["home"] in by_abbr and game["away"] in by_abbr
    ]
    abbrs = [team["abbr"] for team in teams]
    index = {abbr: slot for slot, abbr in enumerate(abbrs)}
    conferences: dict[str, list[int]] = {}
    divisions: dict[tuple, list[int]] = {}
    for slot, team in enumerate(teams):
        conferences.setdefault(team.get("conferenceAbbrev") or "", []).append(slot)
        divisions.setdefault((team.get("conferenceAbbrev") or "", team.get("divisionAbbrev") or ""), []).append(slot)

    def current_hits() -> dict[str, tuple[int, int]]:
        ranks = division_ranks(teams)
        seeds = official_seeds(teams)
        found = {}
        for team in teams:
            made = seeds.get(team["abbr"], 99) <= 8
            title = ranks.get(team["abbr"]) == 1
            found[team["abbr"]] = (SIMS if made else 0, SIMS if title else 0)
        return found

    if not pending:
        return current_hits()

    rng = random.Random(2026)
    base_pts = [int(team["points"]) for team in teams]
    base_rw = [int(team["rw"]) for team in teams]
    base_row = [int(team["row"]) for team in teams]
    base_wins = [int(team["wins"]) for team in teams]
    matchups = []
    for game in pending:
        home_i = index[game["home"]]
        away_i = index[game["away"]]
        prob = home_win_prob(strength.get(game["home"], 0.5), strength.get(game["away"], 0.5))
        matchups.append((home_i, away_i, prob))
    hits = [0] * len(teams)
    titles = [0] * len(teams)

    def key(slot: int, pts: list[int], rw: list[int], row: list[int], wins: list[int]) -> tuple:
        return (-pts[slot], -rw[slot], -row[slot], -wins[slot])

    for _ in range(SIMS):
        pts = base_pts[:]
        rw = base_rw[:]
        row = base_row[:]
        wins = base_wins[:]
        for home_i, away_i, prob in matchups:
            home_wins = rng.random() < prob
            extra = rng.random() < OT_RATE
            winner, loser = (home_i, away_i) if home_wins else (away_i, home_i)
            pts[winner] += 2
            wins[winner] += 1
            if extra:
                pts[loser] += 1
                row[winner] += 1
            else:
                rw[winner] += 1
                row[winner] += 1
        for conf, members in conferences.items():
            inside: set[int] = set()
            for (conference, _division), slots in divisions.items():
                if conference != conf:
                    continue
                ranked = sorted(slots, key=lambda slot: key(slot, pts, rw, row, wins))
                inside.update(ranked[:3])
                if ranked:
                    titles[ranked[0]] += 1
            rest = sorted((slot for slot in members if slot not in inside), key=lambda slot: key(slot, pts, rw, row, wins))
            for slot in inside:
                hits[slot] += 1
            for slot in rest[:2]:
                hits[slot] += 1
    return {abbrs[slot]: (hits[slot], titles[slot]) for slot in range(len(abbrs))}


def form_for(abbr: str, games: list[dict]) -> dict:
    done = []
    for game in games:
        if game["gameType"] != 2 or game["state"] not in FINAL_STATES:
            continue
        if abbr not in (game["home"], game["away"]) or game["homeScore"] is None:
            continue
        us = game["homeScore"] if game["home"] == abbr else game["awayScore"]
        them = game["awayScore"] if game["home"] == abbr else game["homeScore"]
        done.append((game["date"] or "", game["id"] or 0, us, them, result_for(abbr, game)))
    done.sort()
    last = done[-3:]
    wins = losses = otl = 0
    diff = 0
    for _date, _id, us, them, result in last:
        diff += int(us) - int(them)
        if result == "W":
            wins += 1
        elif result == "OTL":
            otl += 1
        else:
            losses += 1
    return {
        "games": len(last),
        "diff": diff,
        "record": wlt(wins, losses, otl) if last else "—",
    }


def form_direction(diff: int) -> str:
    if diff > 0:
        return "up"
    if diff < 0:
        return "down"
    return "flat"


def power_raw(team: dict, form: dict) -> float:
    pct = team.get("pointPct")
    base = 0.0 if pct is None else (float(pct) - 0.5) * 100
    recent = (form["diff"] / form["games"]) if form["games"] else 0.0
    return base * 0.72 + recent * 1.15


def power_index(raw: float) -> int:
    return int(max(1, min(99, round(50 + raw))))


def signed(value: int | float | None) -> str:
    if value is None:
        return "—"
    number = int(value) if float(value) == int(value) else value
    if isinstance(number, int):
        return f"{number:+d}"
    return f"{number:+.1f}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    text = f"{float(value):.3f}"
    return text[1:] if text.startswith("0") else text


def fmt_start(iso: str | None) -> str:
    if not iso:
        return ""
    stamp = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
    hour = stamp.strftime("%I").lstrip("0") or "12"
    return f"{stamp.strftime('%a, %b')} {stamp.day} · {hour}:{stamp.strftime('%M %p')}"


def status_of(game: dict) -> str:
    if game["state"] in FINAL_STATES:
        if game.get("periodType") == "SO":
            return "Final/SO"
        if game.get("ot"):
            return "Final/OT"
        return "Final"
    if game["state"] in LIVE_STATES:
        return "Live"
    return fmt_start(game.get("start")) or (game.get("date") or "")


def load_schedules(abbrs: list[str], season: int) -> dict[str, dict]:
    found: dict[str, dict] = {}

    def pull(abbr: str) -> tuple[str, dict]:
        payload = try_fetch(f"https://api-web.nhle.com/v1/club-schedule-season/{abbr}/{season}")
        return abbr, payload or {"games": []}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for abbr, payload in pool.map(pull, abbrs):
            found[abbr] = payload
    return found


def season_length(games: list[dict], abbrs: list[str]) -> int:
    counts = {abbr: 0 for abbr in abbrs}
    for game in games:
        if game["gameType"] != 2:
            continue
        if game["home"] in counts:
            counts[game["home"]] += 1
        if game["away"] in counts:
            counts[game["away"]] += 1
    return max(counts.values()) if any(counts.values()) else 82


def attach_remaining(teams: list[dict], games: list[dict], season_games: int) -> None:
    for team in teams:
        left = sum(
            1 for game in games
            if game["gameType"] == 2 and game["state"] not in FINAL_STATES and team["abbr"] in (game["home"], game["away"])
        )
        team["gr"] = left if games else max(0, season_games - int(team.get("gp") or 0))
        team["seasonGames"] = season_games
        finish_rates(team, season_games)


def player_name(raw: dict) -> str:
    return f"{loc(raw.get('firstName'))} {loc(raw.get('lastName'))}".strip()


def toi_label(seconds: float | None) -> str:
    if not seconds:
        return "—"
    total = int(round(float(seconds)))
    return f"{total // 60}:{total % 60:02d}"


def save_pct(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1:
        number = number / 100
    return round(number, 3)


def build_players(roster: dict, stats: dict, stats_label: str) -> dict:
    by_id = {int(skater["playerId"]): skater for skater in stats.get("skaters") or []}
    goalie_stats = {int(goalie["playerId"]): goalie for goalie in stats.get("goalies") or []}

    def skater_row(player: dict) -> dict:
        stat = by_id.get(int(player["id"])) or {}
        gp = int(stat.get("gamesPlayed") or 0)
        return {
            "id": player.get("id"),
            "name": player_name(player),
            "position": player.get("positionCode") or stat.get("positionCode") or "",
            "headshot": player.get("headshot") or stat.get("headshot") or "",
            "gp": gp if stat else None,
            "goals": stat.get("goals") if stat else None,
            "assists": stat.get("assists") if stat else None,
            "points": int(stat.get("points") or 0) if stat else None,
            "plusMinus": stat.get("plusMinus") if stat else None,
            "toi": toi_label(stat.get("avgTimeOnIcePerGame")) if stat else "—",
        }

    forwards = [skater_row(player) for player in roster.get("forwards") or []]
    defense = [skater_row(player) for player in roster.get("defensemen") or []]
    forwards.sort(key=lambda player: (-(player["points"] if player["points"] is not None else -1), player["name"]))
    defense.sort(key=lambda player: (-(player["points"] if player["points"] is not None else -1), player["name"]))
    goalies = []
    for player in roster.get("goalies") or []:
        stat = goalie_stats.get(int(player["id"])) or {}
        goalies.append({
            "id": player.get("id"),
            "name": player_name(player),
            "headshot": player.get("headshot") or stat.get("headshot") or "",
            "gp": stat.get("gamesPlayed"),
            "wins": stat.get("wins"),
            "losses": stat.get("losses"),
            "otl": stat.get("overtimeLosses"),
            "sv": save_pct(stat.get("savePercentage")),
            "gaa": stat.get("goalsAgainstAverage"),
            "so": stat.get("shutouts"),
        })
    goalies.sort(key=lambda player: (-(player["gp"] or 0), player["name"]))
    played_forwards = [player for player in forwards if player["gp"]]
    played_defense = [player for player in defense if player["gp"]]
    return {
        "label": stats_label,
        "forwards": (played_forwards or forwards)[:12],
        "defense": (played_defense or defense)[:8],
        "goalies": goalies,
    }


def load_people(abbrs: list[str], target: int, prior_id: int, label: str, prior_label: str) -> dict:
    found = {}

    def pull(abbr: str):
        empty = {"label": "Roster feed was unavailable on this refresh.", "forwards": [], "defense": [], "goalies": []}
        roster = try_fetch(f"https://api-web.nhle.com/v1/roster/{abbr}/{target}") or try_fetch(
            f"https://api-web.nhle.com/v1/roster/{abbr}/current"
        )
        if not roster:
            return abbr, empty
        current_stats = try_fetch(f"https://api-web.nhle.com/v1/club-stats/{abbr}/{target}/2") or {}
        if current_stats.get("skaters") or current_stats.get("goalies"):
            return abbr, build_players(roster, current_stats, f"{label} regular season")
        prior_stats = try_fetch(f"https://api-web.nhle.com/v1/club-stats/{abbr}/{prior_id}/2") or {}
        return abbr, build_players(
            roster,
            prior_stats,
            f"{prior_label} numbers. They reset once the regular season starts.",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(pull, abbr) for abbr in abbrs]
        for future in as_completed(futures):
            abbr, players = future.result()
            found[abbr] = players
    return found


def rgba(hex_color: str, alpha: float) -> str:
    color = hex_color.lstrip("#")
    if len(color) != 6:
        color = "008e97"
    red, green, blue = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def theme_for(abbr: str) -> tuple[str, str, str, str]:
    if abbr in THEMES:
        return THEMES[abbr]
    digest = hashlib.md5(abbr.encode()).hexdigest()
    return (f"#{digest[:6]}", f"#{digest[6:12]}", "#111111", "#d0d7de")


def ensure_pages(teams: list[dict]) -> None:
    template = (ROOT / "templates" / "team.html").read_text()
    for team in teams:
        primary, accent, deep, powder = theme_for(team["abbr"])
        replacements = {
            "{{PRIMARY_WASH}}": rgba(primary, 0.40),
            "{{ACCENT_WASH}}": rgba(accent, 0.24),
            "{{ACCENT_SOFT}}": rgba(accent, 0.16),
            "{{PRIMARY}}": primary,
            "{{ACCENT}}": accent,
            "{{DEEP}}": deep,
            "{{POWDER}}": powder,
            "{{ABBR}}": team["abbr"],
            "{{NAME}}": full_name(team),
            "{{LOGO}}": (team.get("logo") or "").replace("&", "&amp;").replace('"', "&quot;"),
        }
        html = template
        for key, value in replacements.items():
            html = html.replace(key, value)
        dest = ROOT / "teams" / team["abbr"].lower() / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_text() != html:
            dest.write_text(html)


def row_public(team: dict, **extra) -> dict:
    row = {
        "abbr": team["abbr"],
        "name": full_name(team),
        "nickname": team.get("common") or team.get("name") or team["abbr"],
        "logo": team.get("logo") or "",
        "conference": conf_short(team),
        "conferenceAbbrev": team.get("conferenceAbbrev") or "",
        "division": team.get("division") or "",
        "divisionAbbrev": team.get("divisionAbbrev") or "",
        "record": team.get("record") or "0-0-0",
        "gp": team.get("gp"),
        "wins": team.get("wins"),
        "losses": team.get("losses"),
        "otl": team.get("otl"),
        "points": team.get("points"),
        "pointPct": team.get("pointPct"),
        "rw": team.get("rw"),
        "row": team.get("row"),
        "gf": team.get("gf"),
        "ga": team.get("ga"),
        "diff": team.get("diff"),
        "streak": team.get("streak") or "—",
        "l10": team.get("l10") or "—",
        "l10Points": team.get("l10Points"),
        "home": team.get("home"),
        "road": team.get("road"),
        "homePoints": team.get("homePoints"),
        "roadPoints": team.get("roadPoints"),
        "gr": team.get("gr"),
        "pace": team.get("pace"),
        "xpts": team.get("xpts"),
        "otWins": team.get("otWins"),
        "soWins": team.get("soWins"),
        "playoffPct": team.get("playoffPct"),
    }
    row.update(extra)
    return row


def path_summary(focus: dict, teams: list[dict], ranks: dict[str, int]) -> dict:
    abbr = focus["abbr"]
    nick = focus.get("common") or abbr
    division = focus.get("division") or "Division"
    short = conf_short(focus)
    division_teams = sorted(
        (team for team in teams if team.get("divisionAbbrev") == focus.get("divisionAbbrev") and team.get("conferenceAbbrev") == focus.get("conferenceAbbrev")),
        key=tie_key,
    )
    outsiders = sorted(
        (
            team for team in teams
            if team.get("conferenceAbbrev") == focus.get("conferenceAbbrev") and ranks.get(team["abbr"], 99) > 3
        ),
        key=tie_key,
    )
    seeds = official_seeds(teams)
    in_field = seeds.get(abbr, 99) <= 8

    def describe(contenders: list[dict], spots: int, title: str, empty_detail: str) -> dict:
        if not any(team["abbr"] == abbr for team in contenders):
            return {"title": title, "in": True, "value": "In", "points": 0, "detail": empty_detail, "rival": None}
        index = next(i for i, team in enumerate(contenders) if team["abbr"] == abbr)
        if index < spots:
            rival = contenders[spots] if len(contenders) > spots else None
            cushion = (focus["points"] - rival["points"]) if rival else focus["points"]
            rival_name = rival.get("common") if rival else "the field"
            return {
                "title": title, "in": True, "value": gap_text(True, cushion), "points": cushion,
                "detail": f"{cushion} points up on {rival_name}." if rival else "Every other club is behind.",
                "rival": rival["abbr"] if rival else None,
            }
        last_in = contenders[spots - 1]
        back = last_in["points"] - focus["points"]
        return {
            "title": title, "in": False, "value": gap_text(False, back), "points": back,
            "detail": f"{last_in.get('place') or last_in.get('common')} holds the last spot on {last_in['points']} points. The {nick} are {back} back.",
            "rival": last_in["abbr"],
        }

    division_path = describe(
        division_teams, 3, f"{division} top three",
        f"The {nick} are inside the {division} three, which is an automatic playoff berth.",
    )
    wildcard = describe(
        outsiders, 2, f"{short} wild card",
        f"A wild card is not required. The {nick} are already inside the division's top three.",
    )
    if division_path["in"] or wildcard["in"]:
        easier = division_path if division_path["in"] else wildcard
        if division_path["in"] and wildcard["in"]:
            easier = division_path if division_path["points"] >= wildcard["points"] else wildcard
    else:
        easier = division_path if division_path["points"] <= wildcard["points"] else wildcard
    return {"division": division_path, "wildcard": wildcard, "easier": easier, "inField": in_field}


def back_to_back(dates: list) -> int:
    parsed = []
    for value in dates:
        try:
            parsed.append(datetime.fromisoformat(value).date())
        except ValueError:
            continue
    return sum(1 for prev, cur in zip(parsed, parsed[1:]) if (cur - prev).days == 1)


def game_view(game: dict, focus: str, teams: dict[str, dict], strength: dict[str, float], focus_dates: list[str]) -> dict:
    opp = game["away"] if game["home"] == focus else game["home"]
    opp_team = teams.get(opp) or {}
    focus_team = teams.get(focus) or {}
    home_prob = home_win_prob(strength.get(game["home"], 0.5), strength.get(game["away"], 0.5))
    focus_prob = home_prob if game["home"] == focus else 1 - home_prob
    b2b = False
    if game["date"] in focus_dates:
        pos = focus_dates.index(game["date"])
        if pos > 0:
            try:
                prev = datetime.fromisoformat(focus_dates[pos - 1]).date()
                cur = datetime.fromisoformat(game["date"]).date()
                b2b = (cur - prev).days == 1
            except ValueError:
                b2b = False
    us = game["homeScore"] if game["home"] == focus else game["awayScore"]
    them = game["awayScore"] if game["home"] == focus else game["homeScore"]
    return {
        "id": game["id"],
        "date": game["date"],
        "start": game["start"],
        "state": game["state"],
        "venue": game["venue"],
        "isHome": game["home"] == focus,
        "opponent": {
            "abbr": opp,
            "name": full_name(opp_team) if opp_team else opp,
            "common": opp_team.get("common") or opp,
            "logo": (game["awayLogo"] if game["home"] == focus else game["homeLogo"]) or opp_team.get("logo") or "",
            "division": opp_team.get("division") or "",
            "pointPct": opp_team.get("pointPct"),
        },
        "winPct": round(focus_prob * 100, 1),
        "homeWinPct": round(home_prob * 100, 1),
        "awayWinPct": round((1 - home_prob) * 100, 1),
        "homeAbbr": game["home"],
        "awayAbbr": game["away"],
        "homeScore": game["homeScore"],
        "awayScore": game["awayScore"],
        "usScore": us,
        "themScore": them,
        "ot": game["ot"],
        "backToBack": b2b,
        "divisionGame": opp_team.get("divisionAbbrev") == focus_team.get("divisionAbbrev") and opp_team.get("conferenceAbbrev") == focus_team.get("conferenceAbbrev"),
        "conferenceGame": opp_team.get("conferenceAbbrev") == focus_team.get("conferenceAbbrev"),
        "result": result_for(focus, game) if game["state"] in FINAL_STATES else None,
        "final": game["state"] in FINAL_STATES,
    }


def next_game(abbr: str, games: list[dict]) -> tuple[str, str]:
    upcoming = [
        game for game in games
        if abbr in (game["home"], game["away"]) and game["state"] not in FINAL_STATES and game["gameType"] in {1, 2}
    ]
    regular = [game for game in upcoming if game["gameType"] == 2]
    game = (regular or upcoming or [None])[0]
    if not game:
        return "—", "No game posted."
    home = game["home"] == abbr
    opp = game["away"] if home else game["home"]
    label = f"{'vs' if home else '@'} {opp}"
    kind = "Exhibition" if game["gameType"] == 1 else "Regular season"
    return label, f"{kind} · {status_of(game)}"


def week_games(games: list[dict], start, end, teams: dict[str, dict], show_record: bool) -> list[dict]:
    rows = []
    for game in games:
        if not game.get("date"):
            continue
        try:
            day = datetime.fromisoformat(game["date"]).date()
        except ValueError:
            continue
        if day < start or day > end:
            continue
        if game["home"] not in teams or game["away"] not in teams:
            continue
        rows.append(game_card(game, teams, show_record))
    rows.sort(key=lambda game: (game.get("date") or "", game.get("id") or 0))
    return rows


def game_card(game: dict, teams: dict[str, dict], show_record: bool) -> dict:
    def side(abbr: str, score, logo: str) -> dict:
        team = teams.get(abbr) or {}
        return {
            "abbr": abbr,
            "name": full_name(team) if team else abbr,
            "nickname": team.get("common") or abbr,
            "logo": logo or team.get("logo") or "",
            "record": team.get("record") if show_record else "",
            "score": "" if score is None else score,
        }
    home = side(game["home"], game["homeScore"], game.get("homeLogo") or "")
    away = side(game["away"], game["awayScore"], game.get("awayLogo") or "")
    completed = game["state"] in FINAL_STATES and game["homeScore"] is not None
    if completed:
        home["winner"] = game["homeScore"] > game["awayScore"]
        away["winner"] = game["awayScore"] > game["homeScore"]
    return {
        "id": game["id"],
        "date": game["date"],
        "status": status_of(game),
        "live": game["state"] in LIVE_STATES,
        "completed": completed,
        "exhibition": game["gameType"] == 1,
        "venue": game.get("venue") or "",
        "broadcast": game.get("broadcast") or "",
        "home": home,
        "away": away,
    }


def load_baseline(week_key: str) -> dict:
    if not LEAGUE_PATH.exists():
        return {}
    try:
        old = json.loads(LEAGUE_PATH.read_text())
    except json.JSONDecodeError:
        return {}
    saved = old.get("rankBaseline") if isinstance(old.get("rankBaseline"), dict) else {}
    if old.get("rankBaselineWeek") == week_key and saved:
        return {abbr: int(rank) for abbr, rank in saved.items()}
    frozen = {}
    for row in old.get("powerRankings") or []:
        if row.get("abbr") and row.get("rank"):
            frozen[row["abbr"]] = int(row["rank"])
    return frozen


def stable(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("generatedAt", None)
    return json.dumps(copy, sort_keys=True, separators=(",", ":"))


def unchanged(path: Path, payload: dict) -> bool:
    if not path.exists():
        return False
    try:
        previous = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False
    return stable(previous) == stable(payload)


def decorate_conference(teams: list[dict], focus: str, vs_focus: dict[str, int]) -> list[dict]:
    ranks = division_ranks(teams)
    ordered = sorted(
        (team for team in teams if team.get("conferenceAbbrev") == (next(item for item in teams if item["abbr"] == focus).get("conferenceAbbrev"))),
        key=tie_key,
    )
    seeds = official_seeds(teams)
    inside = {team["abbr"] for team in ordered if seeds.get(team["abbr"], 99) <= 8}
    in_rows = [team for team in ordered if team["abbr"] in inside]
    out_rows = [team for team in ordered if team["abbr"] not in inside]
    rows = []
    for group, field in ((in_rows, True), (out_rows, False)):
        for team in group:
            row = row_public(
                team,
                inField=field,
                path=path_label(team, ranks, seeds.get(team["abbr"], 99)),
                divisionRank=ranks.get(team["abbr"]),
                vsFocus=vs_focus.get(team["abbr"], 0),
                isFocus=team["abbr"] == focus,
                isCut=False,
            )
            rows.append(row)
    if rows:
        last_in = max((index for index, row in enumerate(rows) if row["inField"]), default=-1)
        if last_in >= 0:
            rows[last_in]["isCut"] = True
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_focus(abbr: str, ctx: dict) -> dict:
    shown = ctx["shown_by"][abbr]
    current = ctx["current_by"][abbr]
    teams_shown = ctx["shown"]
    teams_now = ctx["current"]
    mode = ctx["mode"]
    ranks = ctx["ranks"]
    label = ctx["label"]
    prior_label = ctx["prior_label"]
    timeframe = ctx["timeframe"]
    nick = shown.get("common") or abbr
    club_name = full_name(shown)
    short = conf_short(shown)
    division = shown.get("division") or "Division"
    paths = path_summary(shown, teams_shown, ranks)
    easier = paths["easier"]
    magic = magic_payload(current, teams_now, mode == "over", paths["inField"] if mode != "preview" else False)
    eliminated = mode != "preview" and (magic.get("kind") == "eliminated" or eliminated_now(current, teams_now))
    if (current.get("clinch") or "") in CLINCHED:
        eliminated = False
    odds_pct = shown.get("playoffPct")
    odds = {
        "percent": odds_pct,
        "sims": SIMS,
        "note": (
            "Each remaining game is simulated from points percentage, shrunk toward .500, "
            "with a home-ice bump. About 23% of games go past regulation and give the loser a point. "
            "Not a betting line."
        ),
    }
    if mode == "preview":
        odds["note"] = (
            "Full season, simulated from last year's points percentage shrunk toward .500, "
            "plus home ice, on this year's schedule. About 23% of games go past regulation. "
            "The number moves once this season's points replace last year's. Not a betting line."
        )
    today = ctx["today"]
    remaining_games = [
        game for game in ctx["games"]
        if game["gameType"] == 2 and game["state"] not in FINAL_STATES and abbr in (game["home"], game["away"])
    ]
    opener_raw = remaining_games[0] if remaining_games else None
    opener = None
    if opener_raw:
        opener_day = datetime.fromisoformat(opener_raw["date"]).date()
        opp = opener_raw["away"] if opener_raw["home"] == abbr else opener_raw["home"]
        opp_team = ctx["shown_by"].get(opp) or ctx["current_by"].get(opp) or {}
        opener = {
            "label": fmt_start(opener_raw["start"]) or opener_raw["date"],
            "days": (opener_day - today).days,
            "isHome": opener_raw["home"] == abbr,
            "opponentName": opp_team.get("place") or full_name(opp_team) or opp,
        }
    if mode == "preview" and opener:
        days = opener["days"]
        when = "tonight" if days == 0 else "tomorrow" if days == 1 else f"in {max(days, 0)} days"
        where = "at home against" if opener["isHome"] else "at"
        if paths["inField"]:
            last = f"Last spring they were in, {easier['value']} on the {easier['title']}."
        else:
            last = f"Last spring they finished {easier['points']} points back of the easier route in, the {easier['title']}."
        narrative = {
            "status": "preview",
            "kicker": f"{label} opens {opener['label']}",
            "headline": f"Puck drop {when}",
            "blurb": (
                f"The {nick} open {where} {opener['opponentName']} on {opener['label']}. "
                f"A full-season simulation gives them a {odds_pct}% chance to still be playing in April. {last}"
            ),
        }
        meters = {
            "primary": {
                "label": "Points back last spring",
                "value": easier["value"],
                "sub": easier["title"],
                "heatLabel": f"{prior_label} points rate",
                "heat": round(float(shown["pointPct"] or 0) * 100),
                "heatText": fmt_pct(shown["pointPct"]),
            },
            "third": {
                "label": "Days to opening night",
                "value": str(max(days, 0)),
                "sub": opener["label"],
                "note": "Exhibition games do not count. The standings start at zero on opening night.",
            },
        }
    elif eliminated:
        narrative = {
            "status": "eliminated",
            "kicker": f"{label} playoff race",
            "headline": "See ya next season",
            "blurb": f"The {club_name} have been mathematically eliminated from the Stanley Cup playoffs.",
        }
        meters = {
            "primary": {
                "label": "Points back of the cut line",
                "value": "OUT",
                "sub": shown["record"],
                "heatLabel": "Last 10 points rate",
                "heat": round(100 * (shown["l10Points"] or 0) / 20),
                "heatText": f"{shown['l10Points'] or 0}/20",
            },
            "third": magic,
        }
    elif paths["inField"]:
        narrative = {
            "status": "in",
            "kicker": "Holding a playoff spot",
            "headline": "In the field",
            "blurb": (
                f"The {nick} are in through the {easier['title']}. "
                f"The cushion is {easier['value']}. Every remaining point is about staying there."
            ),
        }
        meters = {
            "primary": {
                "label": "Points up on the cut line",
                "value": easier["value"],
                "sub": easier["title"],
                "heatLabel": "Last 10 points rate",
                "heat": round(100 * (shown["l10Points"] or 0) / 20),
                "heatText": f"{shown['l10Points'] or 0}/20",
            },
            "third": magic,
        }
    else:
        gap = easier["points"]
        if gap <= 4:
            headline, status = "Right on the cut line", "chasing"
        elif gap <= 10:
            headline, status = "Still in the hunt", "hunting"
        else:
            headline, status = "Long way back", "longshot"
        narrative = {
            "status": status,
            "kicker": f"{short} Conference chase",
            "headline": headline,
            "blurb": (
                f"The {nick} are {gap} points back of the {easier['title']}, the easier of the two routes in. "
                f"The model has them at {odds_pct}% to make it."
            ),
        }
        meters = {
            "primary": {
                "label": "Points back of the easier path",
                "value": easier["value"],
                "sub": easier["title"],
                "heatLabel": "Last 10 points rate",
                "heat": round(100 * (shown["l10Points"] or 0) / 20),
                "heatText": f"{shown['l10Points'] or 0}/20",
            },
            "third": magic,
        }
    if mode == "live" and str(shown.get("streak") or "").startswith("W") and narrative["status"] in {"chasing", "hunting"}:
        narrative["blurb"] += f" They are on a {shown['streak']} run."

    strength = ctx["strength"]
    focus_games = [
        game for game in ctx["games"]
        if game["gameType"] == 2 and abbr in (game["home"], game["away"])
    ]
    dates = [game["date"] for game in focus_games if game.get("date")]
    shown_by = ctx["shown_by"]
    upcoming = [game_view(game, abbr, shown_by, strength, dates) for game in remaining_games[:12]]
    if mode == "preview":
        recent_source = [
            game for game in ctx["prior_games"]
            if game["gameType"] == 2 and game["state"] in FINAL_STATES and abbr in (game["home"], game["away"])
        ][-8:]
    else:
        recent_source = [
            game for game in ctx["games"]
            if game["gameType"] == 2 and game["state"] in FINAL_STATES and abbr in (game["home"], game["away"])
        ][-8:]
    recent = [game_view(game, abbr, shown_by, strength, dates) for game in recent_source]
    preseason = [
        game_view(game, abbr, ctx["current_by"], strength, dates)
        for game in ctx["games"]
        if game["gameType"] == 1 and abbr in (game["home"], game["away"])
    ]
    rooting = []
    for game in remaining_games[:4]:
        view = game_view(game, abbr, shown_by, strength, dates)
        view["interest"] = f"{nick} game"
        view["tagClass"] = "leafs"
        view["note"] = f"A win banks 2 points. An overtime loss still salvages 1. Model has the {nick} at {view['winPct']}%."
        rooting.append(view)
    rival = easier.get("rival")
    if rival and not paths["inField"]:
        rival_games = [
            game for game in ctx["games"]
            if game["gameType"] == 2 and game["state"] not in FINAL_STATES
            and rival in (game["home"], game["away"]) and abbr not in (game["home"], game["away"])
        ]
        if rival_games:
            view = game_view(rival_games[0], rival, shown_by, strength, [rival_games[0]["date"]])
            view["interest"] = "Needs a loss"
            view["tagClass"] = "need"
            view["note"] = f"A loss by {shown_by.get(rival, {}).get('common') or rival} closes the {easier['title']} gap."
            view["backToBack"] = False
            rooting.append(view)

    home_left = sum(1 for game in remaining_games if game["home"] == abbr)
    division_left = 0
    conference_left = 0
    strength_bits = []
    for game in remaining_games:
        opp = game["away"] if game["home"] == abbr else game["home"]
        strength_bits.append(strength.get(opp, 0.5))
        opp_team = ctx["current_by"].get(opp) or {}
        if opp_team.get("divisionAbbrev") == shown.get("divisionAbbrev") and opp_team.get("conferenceAbbrev") == shown.get("conferenceAbbrev"):
            division_left += 1
        if opp_team.get("conferenceAbbrev") == shown.get("conferenceAbbrev"):
            conference_left += 1
    sos = round(sum(strength_bits) / len(strength_bits), 3) if strength_bits else None
    remaining_dates = [game["date"] for game in remaining_games if game.get("date")]

    if mode == "preview":
        chips = [
            {"label": "Last year", "value": shown["record"]},
            {"label": "Points", "value": str(shown["points"])},
            {"label": "Reg. wins", "value": str(shown["rw"])},
            {"label": "Diff", "value": signed(shown["diff"])},
        ]
    else:
        chips = [
            {"label": "Record", "value": shown["record"]},
            {"label": "Points", "value": str(shown["points"])},
            {"label": "RW", "value": str(shown["rw"])},
            {"label": "Diff", "value": signed(shown["diff"])},
        ]
    pace_value = "—" if shown.get("pace") is None else str(shown["pace"])
    kpis = [
        {"label": "Playoff odds", "value": f"{odds_pct}%", "hint": f"{SIMS:,} season sims", "stat": "Odds"},
        {"label": "Easier path", "value": easier["value"], "hint": easier["title"], "stat": "Path"},
        {"label": "Regulation wins", "value": str(shown["rw"]), "hint": "First tiebreaker after points", "stat": "RW"},
        {"label": "Goal diff", "value": signed(shown["diff"]), "hint": f"Expected points {shown['xpts'] if shown.get('xpts') is not None else '—'}", "stat": "Diff"},
        {"label": "Games left", "value": str(len(remaining_games)), "hint": f"{home_left} home · {len(remaining_games) - home_left} road", "stat": "GR"},
        {"label": "Point pace", "value": pace_value, "hint": f"Points rate stretched over {ctx['season_games']} games" if mode != "preview" else f"{prior_label} finish, not a forecast", "stat": "Pace"},
        {"label": "ROW", "value": str(shown["row"]), "hint": "Regulation plus overtime wins. Shootout wins do not count.", "stat": "ROW"},
        {"label": "Schedule", "value": fmt_pct(sos), "hint": "Average opponent strength still on the board", "stat": "SOS"},
    ]
    if mode == "preview":
        home_gap = int(shown["homePoints"]) - int(shown["roadPoints"])
        trends = [
            {"label": "Wild-card gap", "value": paths["wildcard"]["value"], "detail": paths["wildcard"]["detail"], "direction": "down" if not paths["wildcard"]["in"] else "up", "stat": "WC"},
            {"label": f"{division} gap", "value": paths["division"]["value"], "detail": paths["division"]["detail"], "direction": "down" if not paths["division"]["in"] else "up", "stat": "Path"},
            {"label": "Home points", "value": str(shown["homePoints"]), "detail": f"Home record {shown['home']}", "direction": "up" if home_gap > 0 else "down"},
            {"label": "Road points", "value": str(shown["roadPoints"]), "detail": f"Road record {shown['road']}", "direction": "down" if home_gap > 0 else "up"},
            {"label": "Last 10 points", "value": "—" if shown["l10Points"] is None else str(shown["l10Points"]), "detail": f"{shown['l10']} to close the year", "direction": "down" if (shown["l10Points"] or 0) < 10 else "up", "stat": "L10"},
            {"label": "Shootout wins", "value": str(shown["soWins"]), "detail": f"{shown['otWins']} overtime wins sat in ROW. Shootouts did not.", "direction": "flat", "stat": "SO"},
        ]
    else:
        heat = shown["l10Points"] or 0
        trends = [
            {"label": "Last 10 points", "value": str(heat), "detail": f"{shown['l10']} · {heat} of a possible 20", "direction": "up" if heat >= 12 else "down" if heat < 8 else "flat", "stat": "L10"},
            {"label": "Streak", "value": shown["streak"], "detail": "Current run", "direction": "up" if str(shown["streak"]).startswith("W") else "down" if str(shown["streak"]).startswith("L") else "flat"},
            {"label": "Point pace", "value": pace_value, "detail": f"Max still available: {current['maxPoints']}", "direction": "up" if (shown.get("pace") or 0) >= 96 else "down" if shown.get("pace") else "flat", "stat": "Pace"},
            {"label": "Expected points", "value": "—" if shown.get("xpts") is None else str(shown["xpts"]), "detail": "What the goal differential says they should have", "direction": "up" if (shown.get("xpts") or 0) > shown["points"] else "down", "stat": "xPTS"},
            {"label": "Home points", "value": str(shown["homePoints"]), "detail": shown["home"], "direction": "flat"},
            {"label": "Road points", "value": str(shown["roadPoints"]), "detail": shown["road"], "direction": "flat"},
        ]
    conference = decorate_conference(teams_shown, abbr, ctx["vs"].get(abbr, {}))
    division_table = [row for row in conference if row["divisionAbbrev"] == shown.get("divisionAbbrev")]
    division_table.sort(key=lambda row: row.get("divisionRank") or 99)
    for row in division_table:
        row["divisionCut"] = row.get("divisionRank") == 3
    leaders = []
    seen_divs = []
    for row in conference:
        if row.get("divisionRank") == 1 and row["division"] not in seen_divs:
            seen_divs.append(row["division"])
            leaders.append(row)
    compare = list(division_table)
    rival = easier.get("rival")
    if rival and not any(row["abbr"] == rival for row in compare):
        extra = next((row for row in conference if row["abbr"] == rival), None)
        if extra:
            compare.append(extra)
    tiebreak = {
        "rw": shown["rw"], "row": shown["row"], "otWins": shown["otWins"], "soWins": shown["soWins"],
        "otl": shown["otl"], "wins": shown["wins"], "timeframe": timeframe,
        "detail": (
            f"In {timeframe} the {nick} had {shown['wins']} wins, but only {shown['rw']} came in regulation. "
            f"{shown['otWins']} overtime wins count toward ROW. "
            f"{shown['soWins']} shootout {'win does' if shown['soWins'] == 1 else 'wins do'} not. "
            f"{shown['otl']} overtime losses salvaged a point each."
        ),
    }
    ticker = [
        f"{club_name.upper()} {shown['record']}",
        f"{shown['points']} PTS · {fmt_pct(shown['pointPct'])}",
        f"PLAYOFF ODDS {odds_pct}%",
        f"EASIER PATH {easier['value']}",
        f"{len(remaining_games)} GAMES LEFT",
        narrative["headline"],
    ]
    if mode == "preview":
        ticker.insert(0, f"{prior_label} FINISH")
    elif eliminated:
        ticker.append("MATHEMATICALLY ELIMINATED")
    table_blurb = (
        f"{prior_label} final standings. The {label} board is zeros until opening night. "
        "Top three in each division are in. Two wild cards join them."
        if mode == "preview"
        else f"Top three in each {short} division are in. The next two clubs are the wild cards."
    )
    return {
        "generatedAt": ctx["generated"],
        "team": abbr,
        "season": label,
        "seasonId": ctx["target"],
        "mode": mode,
        "timeframe": timeframe,
        "seasonGames": ctx["season_games"],
        "eliminated": eliminated,
        "focus": {
            "abbr": abbr,
            "name": club_name,
            "nickname": nick,
            "logo": shown.get("logo") or "",
            "conference": short,
            "division": division,
        },
        "rules": ["Win = 2 points", "OT / SO loss = 1", f"Top 3 in the {division} or a wild card"],
        "headings": {
            "division": division,
            "leaders": "Division leaders",
            "leadersBlurb": f"These two lead the {short} divisions. Everyone else is chasing the other six berths.",
            "pathsBlurb": f"Finish top three in the {division}, or be one of the two best remaining teams in the {short}.",
            "legendTeam": nick,
            "footer": f"Updated from the NHL’s public API. Not affiliated with the NHL or the {nick}.",
            "footerTiny": "Eight teams in the conference qualify: the top three in each division and two wild cards. A regulation win and an overtime win are both two points. The playoff percentage is a season simulation from points percentage and home ice. It is not a betting line.",
            "conclusion": f"The {club_name} have been mathematically eliminated from the Stanley Cup playoffs.",
            "rootingBlurb": "Win odds use the same points model as the playoff card. Not a betting line, and not a live in-game number.",
        },
        "narrative": narrative,
        "meters": meters,
        "playoffOdds": odds,
        "chips": chips,
        "kpis": kpis,
        "trends": trends,
        "paths": {"division": paths["division"], "wildcard": paths["wildcard"]},
        "conference": conference,
        "divisionTable": division_table,
        "leaders": leaders,
        "compare": compare,
        "compareTitle": f"{timeframe} in the {division}" if mode == "preview" else f"Teams on the {division} board",
        "tableBlurb": table_blurb,
        "seriesLabel": f"vs {abbr}",
        "schedule": upcoming,
        "remaining": {
            "games": len(remaining_games),
            "home": home_left,
            "away": len(remaining_games) - home_left,
            "division": division_left,
            "conference": conference_left,
            "backToBacks": back_to_back(remaining_dates),
            "sos": sos,
        },
        "recent": recent,
        "recentBlurb": f"How {prior_label} ended. None of this carries over." if mode == "preview" else "The stretch that moved the points column.",
        "preseason": preseason,
        "rooting": rooting,
        "tiebreak": tiebreak,
        "players": ctx["people"].get(abbr) or {},
        "ticker": ticker,
        "legend": {
            "in": "Made it last spring" if mode == "preview" else "In a playoff spot",
            "out": "Missed" if mode == "preview" else "Outside",
        },
    }


def build_league(ctx: dict) -> dict:
    shown = ctx["shown"]
    mode = ctx["mode"]
    forms = ctx["forms"]
    raw = ctx["raw"]
    ranks_power = ctx["power_ranks"]
    moves = ctx["moves"]
    order = ctx["order"]
    seeds = ctx["seeds"]
    div_ranks = ctx["ranks"]
    by_conf: dict[str, list] = {}
    for team in shown:
        by_conf.setdefault(team.get("conferenceAbbrev") or "", []).append(team)
    power_rows = []
    for abbr in order:
        team = ctx["shown_by"][abbr]
        form = forms[abbr]
        seed = seeds.get(abbr, 99)
        row = row_public(team)
        row.update({
            "rank": ranks_power[abbr],
            "move": moves.get(abbr, 0),
            "power": power_index(raw[abbr]),
            "seed": seed,
            "path": path_label(team, div_ranks, seed),
            "inField": seed <= 8,
            "formRecord": form["record"],
            "formDiff": form["diff"],
            "formDirection": form_direction(form["diff"]),
            "nextLabel": ctx["next"][abbr][0],
            "nextTitle": ctx["next"][abbr][1],
            "magicValue": ctx["magic"][abbr]["value"],
            "magicKind": ctx["magic"][abbr]["kind"],
            "magicTitle": ctx["magic"][abbr]["title"],
        })
        power_rows.append(row)
    by_abbr = {row["abbr"]: row for row in power_rows}

    def conference_rows(abbrev: str) -> tuple[list[dict], dict | None]:
        clubs = by_conf.get(abbrev) or []
        clubs.sort(key=lambda team: seeds.get(team["abbr"], 99))
        cut = next((team for team in clubs if seeds.get(team["abbr"]) == 8), clubs[7] if len(clubs) > 7 else (clubs[-1] if clubs else None))
        rows = []
        for team in clubs:
            seed = seeds.get(team["abbr"], 99)
            base = by_abbr[team["abbr"]]
            row = dict(base)
            row["seed"] = seed
            row["inField"] = seed <= 8
            row["isCut"] = seed == 8
            row["path"] = path_label(team, div_ranks, seed)
            row["pb"] = points_back(team, cut) if cut else "—"
            rows.append(row)
        return rows, (by_abbr[cut["abbr"]] if cut else None)

    east_key = "E" if "E" in by_conf else sorted(by_conf)[0]
    west_candidates = [key for key in by_conf if key != east_key]
    west_key = "W" if "W" in by_conf else (west_candidates[0] if west_candidates else east_key)
    east_rows, east_cut = conference_rows(east_key)
    west_rows, west_cut = conference_rows(west_key)
    leaders = []
    seen = set()
    for team in sorted(shown, key=lambda item: (item.get("conference") or "", item.get("division") or "")):
        if div_ranks.get(team["abbr"]) == 1 and team.get("division") not in seen:
            seen.add(team.get("division"))
            leaders.append(by_abbr[team["abbr"]])
    clubs = [
        {"abbr": team["abbr"], "name": full_name(team), "nickname": team.get("common") or team["abbr"], "logo": team.get("logo") or ""}
        for team in sorted(shown, key=lambda item: (item.get("division") or "", full_name(item)))
    ]
    monday = ctx["monday"]
    this_week = week_games(ctx["games"], monday, monday + timedelta(days=6), ctx["shown_by"], mode != "preview")
    if not this_week:
        horizon = ctx["today"] + timedelta(days=7)
        this_week = week_games(ctx["games"], ctx["today"], horizon, ctx["shown_by"], mode != "preview")
    last_games = week_games(ctx["games"], monday - timedelta(days=7), monday - timedelta(days=1), ctx["shown_by"], mode != "preview")
    if mode == "preview" and not last_games:
        last_games = week_games(ctx["prior_games"], monday - timedelta(days=7), monday - timedelta(days=1), ctx["shown_by"], True)
    played = [abbr for abbr in order if forms[abbr]["games"]]
    played.sort(key=lambda abbr: (forms[abbr]["diff"],))
    up_abbrs = list(reversed(played[-4:])) if played else []
    up_set = set(up_abbrs)
    down_abbrs = [abbr for abbr in played if abbr not in up_set][:4]
    top = power_rows[0]
    hot = by_abbr[up_abbrs[0]] if up_abbrs else top
    cold = by_abbr[down_abbrs[0]] if down_abbrs else None
    opener = ctx.get("opener_label") or "opening night"
    if mode == "preview":
        headline = f"The {top['nickname']} led the league last spring"
        blurb = (
            f"{ctx['label']} opens {opener}. The board below is the {ctx['prior_label']} finish. "
            f"The {top['nickname']} are No. 1 at {top['record']} with {top['points']} points. "
        )
        if east_cut and west_cut:
            blurb += (
                f"The East's last playoff spot was the {east_cut['nickname']} on {east_cut['points']} points. "
                f"The West's was the {west_cut['nickname']} on {west_cut['points']} points."
            )
    else:
        if hot["formDiff"] > 0 and hot["abbr"] != top["abbr"]:
            headline = f"The {hot['nickname']} are the team on the rise"
        else:
            headline = f"The {top['nickname']} lead the power rankings"
        blurb = (
            f"{len(this_week)} games on this week's slate. "
            f"The {top['nickname']} are No. 1 at {top['record']} with a {signed(top['diff'])} goal differential. "
        )
        if east_cut and west_cut:
            blurb += (
                f"The East's last playoff spot is the {east_cut['nickname']} on {east_cut['points']} points. "
                f"The West's last spot is the {west_cut['nickname']} on {west_cut['points']} points. "
            )
        if hot["formDiff"] > 0:
            blurb += f"The {hot['nickname']} lead the heat check at {hot['formRecord']} and {signed(hot['formDiff'])} goals over the last three games."
        elif cold:
            blurb += f"The {cold['nickname']} are the coldest club at {signed(cold['formDiff'])} over the last three games."
    week_label = f"{ctx['prior_label']} finish" if mode == "preview" else f"Week of {monday.strftime('%b')} {monday.day}"
    ticker = [
        week_label.upper(),
        f"NO. 1 {top['abbr']} {top['record']}",
        f"EAST CUT {east_cut['abbr']} {east_cut['points']} PTS" if east_cut else "EAST",
        f"WEST CUT {west_cut['abbr']} {west_cut['points']} PTS" if west_cut else "WEST",
        f"HOT {hot['abbr']} {signed(hot['formDiff'])} LAST 3",
    ]
    picture_note = "Last spring's finish. " if mode == "preview" else ""
    return {
        "generatedAt": ctx["generated"],
        "season": ctx["label"],
        "mode": mode,
        "weekLabel": week_label,
        "rankBaseline": ctx["baseline"],
        "rankBaselineWeek": ctx["week_key"],
        "ticker": ticker,
        "narrative": {"kicker": week_label, "headline": headline, "blurb": blurb},
        "chips": [
            {"label": "Season", "value": ctx["label"] if mode != "preview" else ctx["prior_label"]},
            {"label": "Games", "value": str(len(this_week))},
            {"label": "Hottest", "value": hot["abbr"]},
            {"label": "East cut", "value": f"{east_cut['abbr']} {east_cut['points']} pts" if east_cut else "—"},
            {"label": "West cut", "value": f"{west_cut['abbr']} {west_cut['points']} pts" if west_cut else "—"},
            {"label": "No. 1", "value": top["abbr"]},
        ],
        "spotlight": {"top": top, "east": east_cut, "west": west_cut},
        "clubs": clubs,
        "powerRankings": power_rows,
        "rankingsBlurb": (
            f"Last spring's points percentage, shrunk toward .500, plus the goal margin over the final three games of {ctx['prior_label']}. "
            "Movement is since this week's order was frozen."
            if mode == "preview"
            else "Points percentage shrunk toward a .500 club, plus the goal margin over the last three games. Movement is since this week's order was frozen."
        ),
        "trending": {"up": [by_abbr[abbr] for abbr in up_abbrs], "down": [by_abbr[abbr] for abbr in down_abbrs]},
        "trendingBlurb": "Goal differential over the last three games. Heating up is the best stretch. Cooling off is the worst.",
        "east": east_rows,
        "west": west_rows,
        "eastBlurb": f"{picture_note}Eight Eastern clubs play on. The line under the eighth seed is the cut line.",
        "westBlurb": f"{picture_note}Eight Western clubs play on. The line under the eighth seed is the cut line.",
        "leaders": leaders,
        "thisWeek": this_week,
        "lastWeek": last_games,
        "weekBlurb": "Puck drops this week, with the score once a game is live or final. Exhibition games do not move the standings." if any(game.get("exhibition") for game in this_week) else "Puck drops this week, with the score once a game is live or final.",
        "lastBlurb": "Final scores from the previous week." if last_games else "No games were posted for the previous week.",
    }


def publish() -> None:
    now = now_local()
    today = now.date()
    target = target_season_id(now)
    prior_id = previous_season_id(target)
    label = season_label(target)
    prior_label = season_label(prior_id)
    print("Standings...", flush=True)
    standings_payload = fetch_json("https://api-web.nhle.com/v1/standings/now")
    standing_rows = standings_payload.get("standings") or []
    if not standing_rows:
        raise RuntimeError("NHL standings feed was empty")
    standings_season = int(standing_rows[0].get("seasonId") or 0)
    probe = loc((standing_rows[0].get("teamAbbrev")))
    print(f"Schedules for {target}...", flush=True)
    if standings_season == target:
        prior_probe = try_fetch(f"https://api-web.nhle.com/v1/club-schedule-season/{probe}/{prior_id}") or {"games": []}
        prior_dates = [
            game.get("gameDate") for game in prior_probe.get("games") or []
            if game.get("gameType") == 2 and game.get("gameDate")
        ]
        prior_rows = standing_rows
        if prior_dates:
            prior_payload = try_fetch(f"https://api-web.nhle.com/v1/standings/{max(prior_dates)}")
            if prior_payload and prior_payload.get("standings"):
                prior_rows = prior_payload["standings"]
    else:
        prior_rows = standing_rows

    prior_teams = teams_from_rows(prior_rows, 82)
    abbrs = [team["abbr"] for team in prior_teams]
    schedules = load_schedules(abbrs, target)
    games = collect_games(schedules)
    season_games = season_length(games, abbrs)
    finals = [game for game in games if game["gameType"] == 2 and game["state"] in FINAL_STATES and game["homeScore"] is not None]
    if standings_season == target and any(int(row.get("gamesPlayed") or 0) > 0 for row in standing_rows):
        current = teams_from_rows(standing_rows, season_games)
        attach_remaining(current, games, season_games)
        mode = "over" if not any(game["gameType"] == 2 and game["state"] not in FINAL_STATES for game in games) else "live"
    elif finals:
        current = zero_teams(prior_teams, season_games)
        apply_results(current, games, season_games)
        mode = "over" if not any(game["gameType"] == 2 and game["state"] not in FINAL_STATES for game in games) else "live"
    else:
        current = zero_teams(prior_teams, season_games)
        for team in current:
            team["gr"] = season_games
            team["maxPoints"] = 2 * season_games
        mode = "preview"

    print(f"Mode {mode}. Prior schedules..." if mode == "preview" else f"Mode {mode}.", flush=True)
    prior_games = []
    if mode == "preview":
        prior_season = standings_season if standings_season != target else prior_id
        prior_games = collect_games(load_schedules(abbrs, prior_season))

    current_by = {team["abbr"]: team for team in current}
    prior_by = {team["abbr"]: team for team in prior_teams}
    shown = prior_teams if mode == "preview" else current
    for team in shown:
        if mode == "preview":
            team["clinch"] = ""
    shown_by = {team["abbr"]: team for team in shown}
    form_games = prior_games if mode == "preview" else games
    forms = {abbr: form_for(abbr, form_games) for abbr in abbrs}
    strength = {team["abbr"]: strength_of(team, prior_by.get(team["abbr"])) for team in current}
    print(f"Simulating {SIMS} seasons...", flush=True)
    odds = simulate_all(current, games, strength)
    for team in shown:
        made, _titles = odds.get(team["abbr"], (0, 0))
        team["playoffPct"] = round(100 * made / SIMS, 1)
    for team in current:
        made, _titles = odds.get(team["abbr"], (0, 0))
        team["playoffPct"] = round(100 * made / SIMS, 1)

    print("Rosters...", flush=True)
    people = load_people(abbrs, target, prior_id, label, prior_label)
    ensure_pages(shown)

    raw = {abbr: power_raw(shown_by[abbr], forms[abbr]) for abbr in abbrs}
    order = sorted(abbrs, key=lambda abbr: (-raw[abbr], -int(shown_by[abbr]["points"]), -int(shown_by[abbr]["diff"]), abbr))
    power_ranks = {abbr: index for index, abbr in enumerate(order, start=1)}
    monday = today - timedelta(days=today.weekday())
    week_key = monday.isoformat()
    baseline = load_baseline(week_key)
    if not baseline:
        baseline = dict(power_ranks)
    moves = {abbr: int(baseline.get(abbr, power_ranks[abbr])) - power_ranks[abbr] for abbr in power_ranks}
    seeds = official_seeds(shown)
    div_ranks = division_ranks(shown)
    vs = {}
    for abbr in abbrs:
        counts: dict[str, int] = {}
        for game in games:
            if game["gameType"] != 2 or game["state"] in FINAL_STATES or abbr not in (game["home"], game["away"]):
                continue
            other = game["away"] if game["home"] == abbr else game["home"]
            counts[other] = counts.get(other, 0) + 1
        vs[abbr] = counts
    magic = {}
    nxt = {}
    for abbr in abbrs:
        if mode == "preview":
            magic[abbr] = {"value": "—", "kind": "", "title": "The clinch number shows up after opening night."}
        else:
            payload = magic_payload(current_by[abbr], current, mode == "over", seeds.get(abbr, 99) <= 8)
            kind = "in" if payload["kind"] == "clinched" else "out" if payload["kind"] == "eliminated" else ""
            magic[abbr] = {"value": payload["value"], "kind": kind, "title": payload.get("note") or ""}
        nxt[abbr] = next_game(abbr, games)
    openers = [
        game for game in games
        if game["gameType"] == 2 and game["state"] not in FINAL_STATES and game.get("date")
    ]
    opener_label = fmt_start(openers[0]["start"]) or openers[0]["date"] if openers else "opening night"
    ctx = {
        "generated": now.isoformat(),
        "today": today,
        "monday": monday,
        "week_key": week_key,
        "target": target,
        "label": label,
        "prior_label": prior_label,
        "timeframe": prior_label if mode == "preview" else label,
        "mode": mode,
        "season_games": season_games,
        "shown": shown,
        "shown_by": shown_by,
        "current": current,
        "current_by": current_by,
        "games": games,
        "prior_games": prior_games,
        "forms": forms,
        "raw": raw,
        "power_ranks": power_ranks,
        "order": order,
        "moves": moves,
        "baseline": baseline,
        "seeds": seeds,
        "ranks": div_ranks,
        "strength": strength,
        "people": people,
        "vs": vs,
        "magic": magic,
        "next": nxt,
        "opener_label": opener_label,
    }
    print("Writing files...", flush=True)
    league = build_league(ctx)
    payloads = [(LEAGUE_PATH, league)]
    for abbr in sorted(abbrs):
        payloads.append((TEAMS_DIR / f"{abbr.lower()}.json", build_focus(abbr, ctx)))
    if all(unchanged(path, payload) for path, payload in payloads):
        print("No standings or schedule changes.")
        return
    for path, payload in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    top = league["powerRankings"][0]
    print(
        f"Wrote league.json and {len(payloads) - 1} team files. "
        f"No. 1 {top['abbr']} {top['record']}. This week {len(league['thisWeek'])} games."
    )


def main() -> None:
    publish()


if __name__ == "__main__":
    main()
