# Shared Valorant VCT Dataset Reference

**INF2003 Database Systems · Team 30 · Dataset examination completed 28 October 2026**  
**Location in repository:** `docs/shared/README.md`  
**Purpose:** One self-contained reference for all group members. Read this before designing SQL tables, MongoDB documents, or backend features. **You do not need to rerun the exploration scripts to discover the CSV structures.**

> **Evidence labels:** **Observed** = verified in the team's saved CSV inventory/profiling/validation reports. **Recommended** = suggested implementation approach, not yet agreed final schema. **Unresolved** = issue found but not conclusively fixed. This is a dataset guide, **not** the application user manual, final ERD, or proof the data has already been fully cleaned.

## 1. Dataset at a glance

- **Source used:** Kaggle dataset identified as `ryanluong1/valorant-champion-tour-2021-2023-data`; the local dataset actually examined covers **six seasons, 2021–2026**. Source slug and season coverage differ.
- **Files:** **131 CSV files**: **21 repeating CSV types × 6 seasons = 126**, plus **5 shared `all_ids/` mapping CSVs**.
- **Approximate input volume:** **1.3 GB** of CSV files, according to the team's inventory (raw files are not duplicated in this README).
- **Existing project locations:**

```text
data/
├── raw/
│   ├── all_ids/                  # global ID and team-name mappings
│   ├── vct_2021/ ... vct_2026/  # same 21 CSV filenames per season
└── cleaned/
    └── shared/                  # intermediate agent selections, NOT final import tables
scripts/data_cleaning/shared/    # exploratory/cleaning scripts (optional for feature users)
docs/shared/                     # this README and saved evidence/diagnostics
frontend/                        # Streamlit frontend
backend/                         # backend services (project design)
database/                        # PostgreSQL and MongoDB implementation (project design)
```

- **Schema coverage:** All six seasons contain the 21 season file types. The audit detected no column-name-set changes for the 14 newly examined types; the seven primary gameplay types were also examined across all six seasons. **Similar headers do not prove identical meaning, completeness, or join safety.**
- **Date limitation:** None of the **21 season-specific types** has an explicit match date or timestamp field. `Year` exists in some global mappings and is inferable from each season folder. **Do not implement an exact date filter using fabricated dates**; add verified external metadata or agree to a season/tournament filter instead.

## 2. The most important concepts: level of each record

| Concept | Meaning | Typical source |
|---|---|---|
| Tournament | One competition/event with `Tournament ID` | `ids/*`, `all_ids/*` |
| Stage | Subdivision of a tournament with `Stage ID` | Tournament hierarchy IDs |
| Match Type | Tournament bracket/context category (`Match Type ID` where available) | Tournament hierarchy IDs |
| **Match series** | A matchup (e.g. best-of-three). Has a **Match ID** | `matches/scores.csv`, ID mapping |
| **Map game** | One played map within a series. Has a **Game ID** | ID mapping, `matches/maps_scores.csv` |
| Player-map performance | Player's statistics for one map; may include side split | `matches/overview.csv` |
| Team-round record | One team's economy/outcome for a round | `matches/eco_rounds.csv`, round-method file |
| Elimination | Who eliminated whom in a numbered round | `matches/rounds_kills.csv` |
| Aggregated statistic | A calculated total, percentage or summary at a specified context | `agents/*`, `players_stats/*`, `All Maps` rows |

**Never confuse Match ID with Game ID.** One match series can have several maps. Counting `matches/scores.csv` rows and counting mapped Game IDs answer different questions.

### 2.1 Conceptual relationship diagram (not a final ERD)

```text
Tournament (Tournament ID, Year)
  └─ Stage (Stage ID; some blank/0 exceptions)
      └─ Match type (Match Type ID in hierarchy mappings)
          └─ Match series (Match ID)
              └─ Map game (Game ID, Map)
                  ├─ Player/map performance (usually no source Game ID)
                  ├─ Map score (no source Game ID)
                  └─ Team/round economy, round outcomes, eliminations

Team (Team ID)  ── used by match, map and round data
Player (Player ID) ── used by player/agent performance
```

**ID-bearing sources:**

- `data/raw/all_ids/all_matches_games_ids.csv` — tournament/stage/match-type identifiers, **Match ID**, **Game ID**, `Map`, **Year**, and names.
- `data/raw/vct_YEAR/ids/tournaments_stages_matches_games_ids.csv` — season game mappings (no `Match Type ID`).
- `data/raw/all_ids/all_tournaments_stages_match_types_ids.csv` — event/stage/type identifiers with **Year**.
- `data/raw/vct_YEAR/ids/tournaments_stages_match_types_ids.csv` — season hierarchy (no Year column).
- `all_ids/all_players_ids.csv`, `all_ids/all_teams_ids.csv`, and season `ids/players_ids.csv`, `ids/teams_ids.csv` — name-to-ID lookups.
- `all_ids/all_teams_mapping.csv` and `matches/team_mapping.csv` — abbreviations/full names, **not** proof that every conflicting name is an alias.

### 2.2 Joining CSVs that don't contain IDs

Most `matches/*`, `players_stats/*` and `agents/*` CSVs **do not include Game ID or Match ID**. The usual starting context for map-game data is:

`Year + Tournament + Stage + Match Type + Match Name + Map`

Match the text context to the season/global ID mapping, then **check that exactly one Game ID** matches before assigning it. For a round dataset, keep `Round Number`, `Team` and/or `Player` as additional attributes. **This composite text key is not always unique.** In 2021–2022, 23 match-map context groups mapped to multiple Game IDs. Never choose an arbitrary first ID or join one source row to every matching ID.

If the source row has no map (`All Maps` rollup, for example), it usually cannot be assigned to one Game ID. Keep it at its original aggregation level. A correct PostgreSQL FK must represent a real, validated relationship—not an invented ID.

## 3. Catalog: what each of the 21 CSV types is for

All paths below are relative to `data/raw/vct_YEAR/`, for **each** YEAR from 2021 through 2026. **Grain is descriptive, not a proven SQL uniqueness constraint.**

| CSV path | Main purpose | Source row level | Important warning |
|---|---|---|---|
| `agents/agents_pick_rates.csv` | Precomputed agent pick percentages | 1 tournament/stage/match-type/map/agent aggregate | Rates are not pick counts; All Maps overlaps |
| `agents/maps_stats.csv` | Map occurrence counts and side win % | 1 tournament/stage/match-type/map aggregate | Avoid summing overlapping scopes |
| `agents/teams_picked_agents.csv` | Team-agent-map win/loss summary | 1 team/agent/map/context aggregate | Same game counted under multiple agents |
| `ids/players_ids.csv` | Player and Player ID lookup | 1 player label/ID mapping row; not automatically unique | Name changes, blank IDs |
| `ids/teams_ids.csv` | Team and Team ID lookup | 1 team label/ID mapping row | Aliases and blank ID in 2021 |
| `ids/tournaments_stages_match_types_ids.csv` | Tournament → stage → match-type hierarchy | 1 hierarchy-context record | Aggregate All Stages/All Match Types; blank hierarchy IDs |
| `ids/tournaments_stages_matches_games_ids.csv` | IDs for match series and their map games | 1 game mapping row | Match ID ≠ Game ID; ambiguous text keys; Stage ID 0 |
| `matches/draft_phase.csv` | Map pick/ban by team | 1 draft action | No Match ID; verify action ordering if needed |
| `matches/eco_rounds.csv` | Economy and outcome for each team and round | 1 team/map/round observation | "3.9k" credits; Loadout Value missing in 2025/2026 |
| `matches/eco_stats.csv` | Pre-aggregated team economy statistics | 1 map/team/economy-type aggregate | Initiated/Won are context totals; validate denominators |
| `matches/kills.csv` | Player-versus-opponent kill breakdown | 1 player/enemy/map/kill-type aggregate | Not a timestamped event feed; many blank values |
| `matches/kills_stats.csv` | Multi-kill, clutch, plant/defuse player statistics | 1 player/map or All Maps summary | Aggregates and blank counters |
| `matches/maps_played.csv` | Map appearance in a match series | 1 listed map game (text-only) | Not a unique key; blank/repeated maps in early years |
| `matches/maps_scores.csv` | Map score and side breakdown | 1 map score row | No Game ID; extra rows vs maps_played in 2021/22 |
| `matches/overview.csv` | Player map performance by attack/defend/both | 1 player/map/side row (plus aggregates) | Use both + real map for map-level picks |
| `matches/rounds_kills.csv` | Round-number elimination observations | 1 elimination with round context | No timestamp or Game ID; verify map association |
| `matches/scores.csv` | Match-series score and result | 1 match series result row | Do not count as individual map games |
| `matches/team_mapping.csv` | Abbreviated ↔ full team names | 1 abbreviation/name mapping row | Not proof of all possible aliases |
| `matches/win_loss_methods_count.csv` | Counts of team round-win/loss methods | 1 map/team count vector | Pre-aggregated; not one row per round |
| `matches/win_loss_methods_round_number.csv` | Round outcome and winning/losing method | 1 team/map/round observation | Paired teams; check uniqueness |
| `players_stats/players_stats.csv` | Player performance by tournament context/agent | 1 player/context/agent aggregate | Not individual map games; missing ratings/clutches |

### 3.1 The five additional global files

All files below are under `data/raw/all_ids/`:

| Filename | Exact fields |
|---|---|
| `all_matches_games_ids.csv` | Tournament, Tournament ID, Stage, Stage ID, Match Type, Match Type ID, Match Name, Match ID, Map, Game ID, Year |
| `all_players_ids.csv` | Player, Player ID |
| `all_teams_ids.csv` | Team, Team ID |
| `all_teams_mapping.csv` | Abbreviated, Full Name |
| `all_tournaments_stages_match_types_ids.csv` | Tournament, Tournament ID, Stage, Stage ID, Match Type, Match Type ID, Year |

### 3.2 Source row counts by season

These are **CSV row counts**, not proven numbers of valid games, unique events, or complete observations. Early years contain more competitions; do not compare years as though their coverage is identical.

| File | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| `agents/agents_pick_rates.csv` | 192,120 | 132,336 | 17,712 | 24,840 | 30,294 | 21,547 |
| `agents/maps_stats.csv` | 8,005 | 5,514 | 738 | 1,035 | 1,122 | 743 |
| `agents/teams_picked_agents.csv` | 224,050 | 131,546 | 11,751 | 15,647 | 18,396 | 11,848 |
| `ids/players_ids.csv` | 11,190 | 7,568 | 284 | 260 | 349 | 284 |
| `ids/teams_ids.csv` | 2,741 | 1,572 | 51 | 44 | 58 | 49 |
| `ids/tournaments_stages_match_types_ids.csv` | 1,777 | 1,076 | 137 | 197 | 202 | 132 |
| `ids/tournaments_stages_matches_games_ids.csv` | 14,489 | 8,864 | 830 | 1,104 | 1,277 | 886 |
| `matches/draft_phase.csv` | 3,378 | 7,432 | 1,898 | 2,604 | 2,988 | 2,052 |
| `matches/eco_rounds.csv` | 363,518 | 358,798 | 33,032 | 34,514 | 25,182 | 28,944 |
| `matches/eco_stats.csv` | 126,250 | 126,110 | 10,830 | 11,350 | 13,940 | 9,440 |
| `matches/kills.csv` | 946,875 | 945,825 | 81,225 | 85,125 | 104,325 | 70,800 |
| `matches/kills_stats.csv` | 125,783 | 126,337 | 10,868 | 11,354 | 13,912 | 9,440 |
| `matches/maps_played.csv` | 14,486 | 8,864 | 830 | 1,104 | 1,277 | 886 |
| `matches/maps_scores.csv` | 14,503 | 8,884 | 830 | 1,104 | 1,277 | 886 |
| `matches/overview.csv` | 599,355 | 379,378 | 34,944 | 46,152 | 53,226 | 36,840 |
| `matches/rounds_kills.csv` | 788,047 | 776,476 | 70,078 | 72,660 | 89,088 | 60,895 |
| `matches/scores.csv` | 7,224 | 3,842 | 331 | 434 | 503 | 342 |
| `matches/team_mapping.csv` | 2,377 | 1,399 | 51 | 44 | 58 | 49 |
| `matches/win_loss_methods_count.csv` | 28,972 | 17,728 | 1,660 | 2,208 | 2,554 | 1,772 |
| `matches/win_loss_methods_round_number.csv` | 580,342 | 359,210 | 35,514 | 46,754 | 53,950 | 37,502 |
| `players_stats/players_stats.csv` | 194,966 | 126,641 | 11,249 | 15,030 | 17,996 | 11,821 |

For reference, the most commonly confused totals are:

- **2021:** 7,224 match-score rows, 14,489 game-ID mapping rows (**14,488 populated unique Game IDs**), 14,503 map-score rows, 599,355 overview rows.
- **2022:** 3,842 match-score rows, 8,864 game-mapping rows, 8,884 map-score rows, 379,378 overview rows.
- **2023:** 331 match-score rows, 830 game-mapping rows.
- **2024:** 434 match-score rows, 1,104 game-mapping rows.
- **2025:** 503 match-score rows, 1,277 game-mapping rows.
- **2026:** 342 match-score rows, 886 game-mapping rows.

## 4. Exact CSV headers — no need to run schema-exploration scripts

The headers below are copied from our exploration output. **Keep the spaces, punctuation and field spelling exactly as shown when reading CSVs**; your database may use cleaner SQL column names after an explicit mapping. Header presence does not mean values are non-null.

### `agents/agents_pick_rates.csv`

`Tournament` · `Stage` · `Match Type` · `Map` · `Agent` · `Pick Rate`

### `agents/maps_stats.csv`

`Tournament` · `Stage` · `Match Type` · `Map` · `Total Maps Played` · `Attacker Side Win Percentage` · `Defender Side Win Percentage`

### `agents/teams_picked_agents.csv`

`Tournament` · `Stage` · `Match Type` · `Map` · `Team` · `Agent` · `Total Wins By Map` · `Total Loss By Map` · `Total Maps Played`

### `ids/players_ids.csv`

`Player` · `Player ID`

### `ids/teams_ids.csv`

`Team` · `Team ID`

### `ids/tournaments_stages_match_types_ids.csv`

`Tournament` · `Tournament ID` · `Stage` · `Stage ID` · `Match Type` · `Match Type ID`

### `ids/tournaments_stages_matches_games_ids.csv`

`Tournament` · `Tournament ID` · `Stage` · `Stage ID` · `Match Type` · `Match Name` · `Match ID` · `Map` · `Game ID`

### `matches/draft_phase.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Team` · `Action` · `Map`

### `matches/eco_rounds.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Round Number` · `Team` · `Loadout Value` · `Remaining Credits` · `Type` · `Outcome`

### `matches/eco_stats.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Team` · `Type` · `Initiated` · `Won`

### `matches/kills.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Player Team` · `Player` · `Enemy Team` · `Enemy` · `Player Kills` · `Enemy Kills` · `Difference` · `Kill Type`

### `matches/kills_stats.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Team` · `Player` · `Agents` · `2k` · `3k` · `4k` · `5k` · `1v1` · `1v2` · `1v3` · `1v4` · `1v5` · `Econ` · `Spike Plants` · `Spike Defuses`

### `matches/maps_played.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map`

### `matches/maps_scores.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Team A` · `Team A Score` · `Team A Attacker Score` · `Team A Defender Score` · `Team A Overtime Score` · `Team B` · `Team B Score` · `Team B Attacker Score` · `Team B Defender Score` · `Team B Overtime Score` · `Duration`

### `matches/overview.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Player` · `Team` · `Agents` · `Rating` · `Average Combat Score` · `Kills` · `Deaths` · `Assists` · `Kills - Deaths (KD)` · `Kill, Assist, Trade, Survive %` · `Average Damage Per Round` · `Headshot %` · `First Kills` · `First Deaths` · `Kills - Deaths (FKD)` · `Side`

### `matches/rounds_kills.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Round Number` · `Eliminator Team` · `Eliminator` · `Eliminator Agent` · `Eliminated Team` · `Eliminated` · `Eliminated Agent` · `Kill Type`

### `matches/scores.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Team A` · `Team B` · `Team A Score` · `Team B Score` · `Match Result`

### `matches/team_mapping.csv`

`Abbreviated` · `Full Name`

### `matches/win_loss_methods_count.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Team` · `Elimination` · `Detonated` · `Defused` · `Time Expiry (No Plant)` · `Eliminated` · `Defused Failed` · `Detonation Denied` · `Time Expiry (Failed to Plant)`

### `matches/win_loss_methods_round_number.csv`

`Tournament` · `Stage` · `Match Type` · `Match Name` · `Map` · `Round Number` · `Team` · `Method` · `Outcome`

### `players_stats/players_stats.csv`

`Tournament` · `Stage` · `Match Type` · `Player` · `Teams` · `Agents` · `Rounds Played` · `Rating` · `Average Combat Score` · `Kills:Deaths` · `Kill, Assist, Trade, Survive %` · `Average Damage Per Round` · `Kills Per Round` · `Assists Per Round` · `First Kills Per Round` · `First Deaths Per Round` · `Headshot %` · `Clutch Success %` · `Clutches (won/played)` · `Maximum Kills in a Single Map` · `Kills` · `Deaths` · `Assists` · `First Kills` · `First Deaths`

## 5. Interpreting the content correctly

### 5.1 Important statistics rules

| Source | Correct interpretation | Do **not** do this |
|---|---|---|
| `matches/overview.csv` | A player has `Side = both`, `attack`, `defend`, plus possible `Map = All Maps` rollup rows. For single-map player/agent statistics use **`Side = both` and a real, nonblank Map**. | Sum all three side records, or treat All Maps as a real map. |
| `matches/scores.csv` | A **series** result (e.g., 2–1). | Treat a series result as a single map. |
| `matches/maps_scores.csv` | A **map** score with team attack/defence side scores. | Assume a guaranteed one-to-one match with `maps_played` or the ID mapping. |
| `agents/agents_pick_rates.csv` | Already-calculated pick-rate **percentages** by competition context. | Add rates as if they were pick counts. |
| `agents/maps_stats.csv` | Map-count and attacker/defender-win **aggregates** at a context. | Sum All Maps and individual map rows or overlapping tournament/stage scopes. |
| `agents/teams_picked_agents.csv` | Per-team/agent/map aggregate counts. | Sum map counts across multiple agents used by the same team/game. |
| `players_stats/players_stats.csv` | Aggregated statistics for player/context/agent; may mix roles/agents. | Assume one record means one map game. |
| `matches/eco_rounds.csv` | Round economy per team with `Type`, `Outcome`, credit strings. | Interpret missing loadout as zero or assume its values are numeric SQL types already. |
| `matches/eco_stats.csv` | Precomputed economy-type totals for map/team. | Count each summary row as a new round. |
| `matches/kills.csv` | Player-vs-enemy kill **summaries**, potentially All Maps. | Treat it as a timestamped log of individual kills. |
| `matches/rounds_kills.csv` | Elimination observations tagged with round number. | Assume events have timestamps or an explicit source Game ID. |
| `matches/win_loss_methods_round_number.csv` | Method and outcome for team/map/round. | Sum both teams as separate rounds. |

### 5.2 Common raw-value formats and recommended transformations

| Raw example | Interpretation / treatment |
|---|---|
| `95%`, `0%`, `44%` | Percentage text: parse numeric and choose one consistent convention (`95` or `0.95`), document it. |
| `3.9k`, `14.4k`, `0.2k` | Credit quantity text: parse using a validated `k → ×1000` rule if needed. |
| Empty string in numeric column | Use `NULL`/missing if source meaning is unknown. **Blank ≠ numeric zero**. |
| `1/5` in `Clutches (won/played)` | Retain both numerator and denominator; optionally derive ratio. |
| `omen, sova` in `Agents` | Potential multiple agents at an aggregate level; **not automatically multiple picks on one Game ID**. |
| `Map = All Maps` | Summary across maps, not a playable map. |
| `Stage = All Stages`, `Match Type = All Match Types` | Aggregate labels, not regular relational entities. |
| `Stage ID = 0` | Unresolved source value in 2026 Kickoff games; **not safe to invent a matching hierarchy ID**. |
| Team/player names that change case/spelling | Use verified IDs/alias mapping; names alone are not stable primary keys. |

### 5.3 Explicit sample records and field meanings

These come from the archived CSV sample output. They are examples, **not recommendations to hardcode values**.

- A mapping in 2024: `Match Name = Gen.G vs Sentinels`, `Match ID = 378662`, `Map = Haven`, `Game ID = 180369`. The same match has another map such as Ascent with a different Game ID. This demonstrates series vs map-game IDs.
- A 2024 player performance: `Player = t3xture`, `Team = Gen.G`, `Agents = jett`, `Map = Haven`, `Rating = 1.6`, `Average Combat Score = 305`. Check `Side` in the actual row before aggregating.
- A 2023 map score: `Team A = Team Liquid`, `Team B = Natus Vincere`, map `Fracture`, score `11–13`. Series result is stored separately.
- A 2023 economy row: `Round Number = 1`, `Team = Team Liquid`, `Loadout Value = 3.6k`, `Remaining Credits = 0.4k`, `Type = Eco: 0-5k`, `Outcome = Win`.
- A 2025 round elimination: `Round Number = 3`, `Eliminator = Jinggg`, `Eliminated = coconut`, agents `raze` and `gekko`, `Kill Type = 2k`. It gives round context but no timestamp.
- The 2026 `Xi Lai Gaming vs NRG` example has inconsistent labels (`Mega Minors` in Team B fields)—see the issue register below.

## 6. Verified findings and unresolved data-quality issues

This table is the **shared issue register**. It records what our scripts found; none of these observations authorises silent deletion or made-up replacements.

| ID | Observed finding | Scope | Handling / status |
|---|---|---|---|
| Q01 | `matches/overview.csv` has three `Side` scopes and `All Maps` aggregate rows. | All seasons | Use `both` + real map for one player-map observation. Do not sum attack+defend+both. |
| Q02 | `All Maps`, `All Stages`, `All Match Types` are aggregate labels; many hierarchy aggregate rows have blank Stage/Match Type IDs. | All seasons | Treat aggregate scopes separately; don't assume blanks always indicate corrupt rows. |
| Q03 | Initial per-map agent cleaning created **272,985** candidate selections; these are not all validated final picks. | 2021–2026 | Preserve raw, candidates and review rows; resolve exceptions before import. |
| Q04 | Game ID matching: 2021 **196 ambiguous of 143,676** candidates, 2022 **40 ambiguous of 88,349**; no missing-ID text matches under this check. | 2021–2022 | Do not arbitrarily assign Game ID; preserve ambiguity diagnostics. |
| Q05 | **23 match-map text keys** correspond to multiple Game IDs; **236 agent candidate rows** affected. Some pairs have same scoreline, some different, and two groups span different Match IDs. | 2021–2022 | Match text alone is not a unique game key. Don't multiply candidates across IDs or drop as duplicates. |
| Q06 | Under current exact duplicate rule, zero repeated same-selection records; **5** player-game groups with multiple agents in 2021 and **13** in 2022; **226** and **72** game IDs respectively have non-10 player/team-pair counts. | 2021–2022 | Inspect anomalies; do not blanket delete. 2021/22 also had 30/27 initial eligible comma-valued `Agents` and 2022 had 10 blank agents. |
| Q07 | Initial 2025 agent candidates cover **1,276** mapped games but season mapping has **1,277**. | 2025 | Investigate during final import validation; do not impute 10 picks. |
| Q08 | 2021 ID mappings include **one Game ID blank**, **411 Player IDs blank**, **one Team ID blank**; 2022 has one blank player ID and 2025 has two. | 2021, 2022, 2025 | Avoid NOT NULL PK/FK assumptions on raw staging records. Distinguish missing source ID from new synthetic key. |
| Q09 | Global vs season hierarchy: **75** of **395** per-season nonmatches have exact year-matched global hierarchy rows. | 2021 5, 2025 5, 2026 65 | Global hierarchy can supplement missing season entries, subject to key/integrity checks. |
| Q10 | **320** 2026 Kickoff game-mapping rows unresolved against both hierarchies; all use `Stage ID = 0`, Stage `Main Event`: China 84, Pacific 80, EMEA 79, Americas 77. | 2026 | Retain games and mark stage relationship unresolved. Do **not** fabricate a valid stage ID. |
| Q11 | 15 reused Player IDs and 5 reused Team IDs show different names across years; not necessarily errors (e.g. case changes). | Cross-season | Identify by validated IDs; store display-name history/aliases only with evidence. |
| Q12 | `maps_scores.csv` has **17** more rows than `maps_played.csv` in 2021 and **20** more in 2022; 2021 `maps_scores` includes blank maps. | 2021–2022 | Do not assume 1:1 join by text or automatic dedup; validate match-map cardinality. |
| Q13 | `agents/*` contains **pre-aggregated** map/pick/win data, often overlapping by scope. | All | Never sum agent pick percentages; don't sum game counts across individual agents without avoiding duplicates. |
| Q14 | `Loadout Value` missing **2,550/25,182** rows in 2025 and **28,944/28,944** rows in 2026; `Remaining Credits` is present in those rows under audit. | 2025–2026 | Treat loadout-derived analysis in 2026 as unsupported from this field; do not use zero as imputation. |
| Q15 | `matches/kills.csv` has roughly **41% blank** `Player Kills`, `Enemy Kills` and `Difference` rows on average across years, but `Kill Type` is populated. | All | Investigate kill-type semantics for each query; don't assume blank=zero or event-level kill. |
| Q16 | Several player-performance metrics have missing values; original overview `Rating` missing rates vary sharply across years. | All | Use nullable numeric types and explain incomplete statistics; do not rank missing as zero. |
| Q17 | Example 2026 match label says `Xi Lai Gaming vs NRG`, but Team B in scores, map scores, draft and economy samples says `Mega Minors`; result label says `NRG won`. | 2026 Valorant Masters London | Genuine cross-file **label discrepancy**. Do not silently equate these names. Resolve via an evidenced team ID/source before team-based analysis. |
| Q18 | No explicit date/timestamp field identified in any season-specific CSV type. | All | Exact date filter requires verified external metadata; filter by **season** or known competition instead if agreed. |
| Q19 | The six-year schema scan found no header-set differences in the 14 remaining file types. | All | Can share reusable schema mappings, but validate semantics and data values by year. |
| Q20 | Round-level files have no explicit Game ID; player/team context may be textual; some textual match-map keys collide. | All | Any MongoDB embedding or SQL join must carry a verified Game ID or mark unresolved association. |

### 6.1 Numbers to remember

- **272,985** initially cleaned agent-selection *candidate* rows across 2021–2026; this is **not** a certified count of final valid agent picks.
- 2021: **143,676** candidates, **143,480** uniquely resolved by the tested text-to-Game-ID method, **196 ambiguous**; 2022: **88,349** candidates, **88,309** uniquely resolved, **40 ambiguous**; 2023–2026: no ambiguous candidates under that specific check.
- **23** match-map text-key groups affect those **236** ambiguous candidate rows. Some scorelines repeat; others differ. A repeated text key is not proof of a duplicate game.
- Early-year player counts: **226** game IDs flagged as not having 10 distinct player/team pairs in 2021 and **72** in 2022 under the candidate-based validation. These are *review flags*, not grounds for discarding the entire game.
- **2025:** initial agent candidates occur for **1,276** mapped game IDs, while there are **1,277** game-mapping rows. Do not fabricate the missing ten selections.
- **Hierarchy audit (27,450 mapping rows):** **27,055** matched the season hierarchy, **75** could be matched using the same-year **global** hierarchy, **320** remain unresolved (all in the 2026 Kickoff tournaments). Exact joins were tested on `Tournament`, `Tournament ID`, `Stage`, `Stage ID`, `Match Type`.
- The unresolved **320** 2026 Kickoff rows have `Stage = Main Event`, `Stage ID = 0`: China **84**, Pacific **80**, EMEA **79**, Americas **77**. `0` might be a placeholder, but the audit did not prove it.
- **2021:** one blank Game ID, **411** blank Player IDs, one blank Team ID in the examined ID mappings. **2022:** one blank Player ID. **2025:** two blank Player IDs.
- `matches/maps_scores.csv` has **17** more rows than `matches/maps_played.csv` in 2021 and **20** more in 2022. This does **not** by itself prove duplicates.
- `matches/eco_rounds.csv` Loadout Value missing **2,550 of 25,182** rows (2025), and **all 28,944** rows (2026). Avoid implying 2026 loadout analytics can be calculated from that field.
- Missing `Rating` values in `matches/overview.csv` vary substantially by season; never rank blank ratings as zero. Approximate missing rate across all overview rows: 2021 **37.2%**, 2022 **0.2%**, 2023 **6.7%**, 2024 **26.2%**, 2025 **7.7%**, 2026 **2.0%**.
- **2026 inconsistent team labels**: `Match Name = Xi Lai Gaming vs NRG`, yet Team B in multiple score/draft/economy/kill-related records is `Mega Minors`; series `Match Result = NRG won`. **Do not assume `NRG` and `Mega Minors` are aliases** without independent evidence.
- No explicit match date/timestamp in the audited 21 season types: exact date filters require verified added metadata or an agreed feature change.

### 6.2 What is final versus not final

**Safe observations:** actual CSV file presence/headers, observed source row counts, documented field-value examples, raw naming inconsistencies, current diagnostic counts.

**Not settled:** global canonical player/team ID policy for all exceptions, ambiguous Game ID assignment, exact 2026 Stage ID 0 meaning, official alias for the NRG/Mega Minors conflict, completed-game eligibility policy, all final PK/FK constraints, chronological dates, database model, and final agent-pick totals. Each feature owner should document their chosen resolution when it affects their work.

## 7. Recommended implementation workflow (not a requirement to use a particular schema)

1. **Choose the feature and dataset grain.** Determine whether each metric counts seasons, tournaments, series, map games, players, individual eliminations, or aggregated summaries.
2. **Design raw staging tables/collections first** (or an equivalent reproducible import). Preserve source filename, source year and original identifiers/strings; log row counts.
3. **Clean and transform.** Convert text numbers/percentages with explicit rules; exclude aggregates when deriving underlying game totals; retain unmatched rows in diagnostics; don't invent IDs.
4. **Define a verified ID mapping.** Resolve `Game ID` only when the join is unambiguous, and enforce cardinality checks so a join does not silently multiply rows.
5. **Implement SQL/NoSQL database functionality.** PostgreSQL should demonstrate a well-reasoned ERD, PK/FK/constraints, insert/update/delete/read, joins, aggregations, relevant indexes, optionally views and transaction examples. MongoDB should demonstrate a justified document model, CRUD and nontrivial queries/aggregations appropriate to its data.
6. **Connect the app.** Streamlit pages use backend services; don't independently compute competing definitions of matches, agent picks and map counts.
7. **Test outputs.** Compare a selection of database query results against known CSV samples; check edge cases, null handling, many-to-many joins, double-counting and performance.
8. **Document any new discovery here.** Do not rerun full-dataset exploration unless a new source or blocking issue warrants it.

### 7.1 PostgreSQL candidates (suggestions only)

Possible structured entities include `Tournament`, `Stage`, `MatchType`, `MatchSeries`, `MapGame`, `Team`, `Player`, `Agent`, `PlayerGamePerformance`. Decide relationships from actual usage and validated identifiers. A raw record with missing Stage ID should not be coerced into a fake mandatory FK. An SQL `JOIN`, `GROUP BY`, view or indexed lookup should count the correct **record grain** and handle nullable values intentionally.

### 7.2 MongoDB candidates (suggestions only)

`matches/eco_rounds.csv`, `matches/rounds_kills.csv`, and `matches/win_loss_methods_round_number.csv` offer round-level content. A collection may store one document per map round, with a nested array of team economies, round outcomes and eliminations; alternatively, split them by document type if that yields better queries or avoids oversized documents. Embed/reference a **verified Game ID**, not a guessed one; preserve raw text context for unresolved joins. `matches/kills.csv` contains per-player/opponent summaries rather than timestamped kill events.

### 7.3 Data-to-feature pointers (teammates select their own)

| Need | Useful files | Main pitfall |
|---|---|---|
| Homepage season totals (tournaments, series, teams) | `ids/*`, `all_ids/*`, `matches/scores.csv` | Distinguish series from map games; decide coverage |
| Top played maps | `ids/tournaments_stages_matches_games_ids.csv`, `matches/maps_played.csv`, `matches/maps_scores.csv` | Use validated distinct game IDs; map text can collide |
| Top agents | `matches/overview.csv`, `agents/agents_pick_rates.csv` | `both` vs side-specific; aggregates and denominators |
| Team/player profiles and statistics | `ids/players_ids.csv`, `ids/teams_ids.csv`, `players_stats/players_stats.csv`, `matches/overview.csv` | Name/ID conflicts and varying aggregate scope |
| Match browsing / map score history | `matches/scores.csv`, `matches/maps_scores.csv`, `all_ids/*` | Text-to-ID cardinality, score row differences |
| Picks and bans | `matches/draft_phase.csv` | No ID in source; text joins |
| Map and attack/defence win patterns | `agents/maps_stats.csv`, `matches/maps_scores.csv` | Overlapping scopes |
| Opponent/agent preferences | `agents/teams_picked_agents.csv`, `matches/overview.csv` | Multi-agent game counts and team aliases |
| Round economy and outcomes | `matches/eco_rounds.csv`, `matches/eco_stats.csv`, `matches/win_loss_methods_round_number.csv` | 2026 loadout missing; ensure game and round association |
| Round kills and matchups | `matches/rounds_kills.csv`, `matches/kills.csv` | Event data vs summary counts; no timestamp |
| Exact date range | **Not directly supported by audited CSV fields** | Needs an additional verified source |

## 8. Minimum verification checks before calling an import complete

- [ ] Store input season/file and count raw, skipped, unmatched, ambiguous and imported rows.
- [ ] Match/Map/Game IDs and join cardinality agree; no accidental fan-out across repeated map names.
- [ ] No aggregate `All Maps`/`All Stages`/`All Match Types` records are counted as independent base games.
- [ ] No unsupported null-to-zero conversion; numeric formats and percentages are consistent.
- [ ] A sample series result agrees with its child map-score rows; anomaly list preserved.
- [ ] Team/player lookup and name policy does not silently hide the 2026 team-label mismatch.
- [ ] PostgreSQL constraints and MongoDB validation are tested on the *cleaned final* schema, not imposed blindly on raw CSV text.
- [ ] Queries and Streamlit page labels explicitly say 'matches (series)' versus 'maps (games)' where applicable.
- [ ] The team's agreed database interfaces and table names are documented separately when finalised.

## 9. Do we submit our exploration scripts?

**Project brief requirement (INF2003):** submit a ZIP of the **data, source code and user manual** with the project deliverables; if the entire submission is too large (>2 GB for LMS), a permitted GitHub link may be used with access configured. The brief does **not explicitly require the stand-alone inventory/profile/diagnostic scripts** used purely for exploration.

- **Optional:** one-off `inventory_homepage.py`, `homepage_profile.py`, `check_unmatched.py`, `validate_homepage_agents.py`, `audit_shared_identifiers.py`, `audit_hierarchy_links.py`, `audit_gameplay_statistics.py`, `audit_remaining_datasets.py` etc. They are useful evidence/reference in Git, but not central to running the final app.
- **Recommended to include:** cleaning/ETL/import scripts **actually necessary to recreate the populated PostgreSQL or MongoDB datasets**, unless equivalent cleaned data and reliable setup/import instructions are supplied.
- **Required project components:** SQL schemas, seed/import and CRUD/query implementations, MongoDB setup/collections/queries, working backend/frontend application and a **user manual** describing environment, configuration and exact run instructions.
- **This README is not the user manual.** It describes dataset meaning; the eventual user manual must explain how to install dependencies, set environment variables, create/populate DBs and launch/use Streamlit.

## 10. Evidence provenance / audit limitations

The group produced (and reviewed) evidence files such as `dataset_inventory.csv`, `homepage_profile.csv`, `agent_validation_summary.csv`, `ambiguous_game_id_summary.csv`, `identifier_audit_summary.csv`, `identifier_cross_season.csv`, `hierarchy_relationship_summary.csv`, `gameplay_statistics_file_audit.csv`, `gameplay_statistics_columns.csv`, `remaining_dataset_file_audit.csv`, `remaining_dataset_column_audit.csv`, and related samples/examples.

**This README is self-contained:** those reports explain where the figures came from but **are not required for teammates to select files, see columns, understand record grain and begin development**. The complete raw CSVs were not copied into the documentation-building environment; findings are based on the saved audit outputs and samples supplied by the team. Feature-specific imports still need validation against raw data.

## 11. Copy this context into an AI chat

> We are Team 30 working on INF2003's Valorant Competitive Intelligence database application, with a Python/Streamlit frontend and PostgreSQL plus MongoDB backends. The dataset contains 131 CSV files: 21 repeating file types for each season 2021–2026 plus five global `all_ids` mappings. This README documents all CSV paths, header schemas, record grain, row counts, key relationships, and previously discovered data-quality problems. **Do not ask me to rerun generic dataset exploration scripts** unless a specific gap blocks implementation. My feature is: **[write assigned feature]**. Select relevant CSVs, propose suitable data models and queries, explain how joins will avoid duplicate counting, and identify only the feature-specific validation still needed. Match ID is a series; Game ID is a map. Many CSVs lack ID columns. `overview` has side splits/All Maps; agent/map summaries overlap. 2021–2022 text map keys are sometimes ambiguous; some 2026 hierarchy Stage IDs are `0`; the 2026 NRG/Mega Minors naming mismatch is unresolved; there are no explicit match dates in the audited CSVs. Do not invent columns, dates, aliases, fixes, final schema, or 'completed' data cleaning. Give implementation steps and tests I can execute in our project.

---

**Last updated:** 28 October 2026 · **Status:** Data discovery completed; final DB import validation and application implementation pending.
