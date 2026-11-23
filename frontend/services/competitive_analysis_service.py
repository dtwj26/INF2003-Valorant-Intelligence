"""Live PostgreSQL + MongoDB service for Competitive Analysis.

These functions return plain dictionaries; Streamlit and database code stay separate.
Match series, map scores, and 5-agent compositions come from PostgreSQL.
Round-by-round outcomes, attack/defence splits, pistol conversions, and economy
categories come from MongoDB (valorant_intelligence.team_game_rounds).
"""

from collections import Counter
from backend.competitive_analysis import repository as repo
from components.agent_names import format_agent_name


class DataServiceError(Exception):
    """The view can show a retry when analysis records are unavailable."""


def get_filters(season=None):
    """Return seasons, teams, tournaments and maps for the scouting controls."""
    try:
        return repo.fetch_filter_options(season)
    except Exception as error:
        raise DataServiceError("Scouting filters could not be loaded.") from error


def _rate(wins, total):
    return round(100 * wins / total, 1) if total else None


def get_analysis(team_id, season, tournament_id="", map_name=""):
    """Return one applied-scope report for all four analysis sections.

    A map filter narrows map/round statistics; supporting series retain full scores.
    Pistol and economy denominators include only recorded opportunities. Missing
    round records are disclosed in coverage rather than replaced with zero wins.
    Recommendations describe the evidence; they do not predict a counter-strategy.
    """
    try:
        pg_games = repo.fetch_team_games_pg(team_id, season, tournament_id, map_name)
        mongo_docs = repo.fetch_round_docs_mongo(
            team_id, season, [g["game_id"] for g in pg_games]
        )
    except Exception as error:
        raise DataServiceError("Opponent analysis could not be loaded.") from error

    matches_by_id = {}
    games = []
    team_name = ""

    for row in pg_games:
        is_team_a = row["team_a_id"] == str(team_id)
        team_name = row["team_a_name"] if is_team_a else row["team_b_name"]
        won = row["map_a_score"] if is_team_a else row["map_b_score"]
        lost = row["map_b_score"] if is_team_a else row["map_a_score"]

        match_entry = matches_by_id.setdefault(
            row["match_id"],
            {
                "id": row["match_id"],
                "date": f"Match #{row['match_id']}",
                "tournament": row["tournament"],
                "team_ids": [row["team_a_id"], row["team_b_id"]],
                "team_names": [row["team_a_name"], row["team_b_name"]],
                "score": [row["series_a_score"], row["series_b_score"]],
                "games": [],
            },
        )
        match_entry["games"].append(
            {"id": str(row["game_id"]), "map": row["map_name"]}
        )

        mongo_doc = mongo_docs.get(row["game_id"], {})
        games.append(
            {
                "id": str(row["game_id"]),
                "map": row["map_name"],
                "match": match_entry,
                "won": won,
                "lost": lost,
                "composition": row["agents"],
                "rounds": mongo_doc.get("rounds", []),
            }
        )

    matches = list(matches_by_id.values())
    round_total = sum(g["won"] + g["lost"] for g in games)
    round_wins = sum(g["won"] for g in games)

    # Map summaries
    maps = []
    for name in sorted({g["map"] for g in games}):
        group = [g for g in games if g["map"] == name]
        wins = sum(g["won"] > g["lost"] for g in group)
        maps.append(
            {
                "name": name,
                "games": len(group),
                "wins": wins,
                "losses": len(group) - wins,
                "win_rate": _rate(wins, len(group)),
            }
        )

    # Individual agent picks & 5-agent compositions
    agents = Counter(agent for g in games for agent in g["composition"])
    compositions = {}
    for game in games:
        key = tuple(game["composition"])
        row = compositions.setdefault(key, {"agents": list(key), "games": 0, "wins": 0})
        row["games"] += 1
        row["wins"] += game["won"] > game["lost"]
    composition_rows = sorted(
        compositions.values(), key=lambda c: (-c["games"], c["agents"])
    )
    for row in composition_rows:
        row.update(
            usage=_rate(row["games"], len(games)),
            win_rate=_rate(row["wins"], row["games"]),
        )

    # Trends (ordered by Match ID since source CSVs have no timestamps)
    trends = []
    for match in sorted(matches, key=lambda m: int(m["id"])):
        group = [g for g in games if g["match"]["id"] == match["id"]]
        total = sum(g["won"] + g["lost"] for g in group)
        won = sum(g["won"] for g in group)
        trends.append(
            {
                "match_id": match["id"],
                "date": match["date"],
                "rounds": total,
                "wins": won,
                "rate": _rate(won, total),
            }
        )

    # MongoDB round, pistol, and economy aggregation
    pistol_wins = pistol_total = conversion_wins = conversion_total = recovery_wins = recovery_total = 0
    atk_wins = atk_total = def_wins = def_total = overtime = 0
    economy = {}
    recorded_rounds = 0
    complete_maps = 0

    for game in games:
        rounds = game["rounds"]
        recorded_rounds += len(rounds)
        complete_maps += len(rounds) == (game["won"] + game["lost"])
        by_number = {r["number"]: r for r in rounds}

        for row in rounds:
            num = row["number"]
            if num <= 12:
                atk_total += 1
                atk_wins += int(bool(row.get("won")))
            elif num <= 24:
                def_total += 1
                def_wins += int(bool(row.get("won")))
            else:
                overtime += 1

            econ = row.get("economy") or {}
            category = econ.get("category") or "Unclassified"
            group = economy.setdefault(category, {"rounds": 0, "wins": 0})
            group["rounds"] += 1
            group["wins"] += int(bool(row.get("won")))

        for number in (1, 13):
            pistol = by_number.get(number)
            following = by_number.get(number + 1)
            if pistol:
                pistol_total += 1
                pistol_wins += int(bool(pistol.get("won")))
                if following:
                    if pistol.get("won"):
                        conversion_total += 1
                        conversion_wins += int(bool(following.get("won")))
                    else:
                        recovery_total += 1
                        recovery_wins += int(bool(following.get("won")))

    economy_rows = [
        {"category": label, **values, "rate": _rate(values["wins"], values["rounds"])}
        for label, values in economy.items()
    ]
    economy_rows.sort(
        key=lambda r: (not r["category"].startswith("Full buy"), r["category"])
    )

    series_wins = sum(
        m["score"][m["team_ids"].index(str(team_id))]
        > m["score"][1 - m["team_ids"].index(str(team_id))]
        for m in matches
    )
    summary = {
        "matches": len(matches),
        "games": len(games),
        "map_wins": sum(g["won"] > g["lost"] for g in games),
        "map_win_rate": _rate(sum(g["won"] > g["lost"] for g in games), len(games)),
        "rounds": round_total,
        "round_wins": round_wins,
        "round_win_rate": _rate(round_wins, round_total),
        "series_wins": series_wins,
    }

    report = {
        "team_id": str(team_id),
        "team_name": team_name,
        "season": int(season),
        "tournament_id": tournament_id,
        "map_name": map_name,
        "summary": summary,
        "maps": maps,
        "sides": {
            "attack": {
                "wins": atk_wins,
                "total": atk_total,
                "rate": _rate(atk_wins, atk_total),
            },
            "defence": {
                "wins": def_wins,
                "total": def_total,
                "rate": _rate(def_wins, def_total),
            },
        },
        "overtime_rounds": overtime,
        "agents": [
            {"name": name, "picks": count, "share": _rate(count, len(games))}
            for name, count in sorted(agents.items(), key=lambda item: (-item[1], item[0]))
        ],
        "compositions": composition_rows,
        "trends": trends,
        "pistol": [
            {"label": label, "wins": won, "total": total, "rate": _rate(won, total)}
            for label, won, total in [
                ("Pistol rounds", pistol_wins, pistol_total),
                ("Next round after pistol win", conversion_wins, conversion_total),
                ("Next round after pistol loss", recovery_wins, recovery_total),
            ]
        ],
        "economy": economy_rows,
        "matches": matches,
        "coverage": {
            "recorded_rounds": recorded_rounds,
            "expected_rounds": round_total,
            "complete_maps": complete_maps,
            "total_maps": len(games),
        },
    }
    report["recommendations"] = _recommendations(report, games)
    return report


def _recommendations(report, games):
    if not games:
        return []
    strongest = max(report["maps"], key=lambda m: (m["win_rate"], m["games"]))
    weakest = min(report["maps"], key=lambda m: (m["win_rate"], -m["games"]))
    composition = report["compositions"][0]
    agent = report["agents"][0]

    def evidence(selected):
        return [{"match_id": g["match"]["id"], "map": g["map"]} for g in selected[:3]]

    return [
        {
            "title": f"Review {strongest['name']} as a map candidate",
            "body": (
                f"{report['team_name']} has {strongest['wins']} wins from {strongest['games']} "
                f"{strongest['name']} games ({strongest['win_rate']:.1f}%) in this scope. "
                "Inspect these matches before deciding how to prepare."
            ),
            "note": "An observed win rate does not establish a reliable ban or pick prediction.",
            "value": f"{strongest['wins']} / {strongest['games']} map wins",
            "detail": strongest["name"] + " / current applied scope",
            "evidence": evidence([g for g in games if g["map"] == strongest["name"]]),
        },
        {
            "title": "Prepare against the most-used composition",
            "body": (
                f"{', '.join(format_agent_name(a) for a in composition['agents'])} appears in {composition['games']} of {len(games)} "
                f"games ({composition['usage']:.1f}% usage). {format_agent_name(agent['name'])} is the most-used "
                f"individual agent ({agent['picks']} / {len(games)} games). Review the map context "
                "before choosing a practice focus."
            ),
            "note": "Usage indicates what to review; it does not establish the best counter-composition.",
            "value": f"{agent['picks']} / {len(games)} games",
            "detail": format_agent_name(agent["name"]) + " selections / team-map denominator",
            "evidence": evidence(
                [g for g in games if g["composition"] == composition["agents"]]
            ),
        },
        {
            "title": (
                f"Review the lower-performing {weakest['name']} games"
                if len(report["maps"]) > 1
                else f"Review the {weakest['name']} round evidence"
            ),
            "body": (
                f"{weakest['name']} shows {weakest['wins']} wins in {weakest['games']} games "
                f"({weakest['win_rate']:.1f}%). Compare the round, pistol and economy evidence "
                "with the source scoreboards before deciding what to practise."
            ),
            "note": "Opponent strength, small samples and missing records can affect these observations.",
            "value": f"{weakest['games']} map games",
            "detail": "Limited scope / no confidence interval inferred",
            "evidence": evidence([g for g in games if g["map"] == weakest["name"]]),
        },
    ]