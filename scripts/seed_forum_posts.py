"""CLI script to populate 18 domain-authentic VCT starter threads into PostgreSQL + MongoDB.

Usage (from repository root):
    python scripts/seed_forum_posts.py
    python scripts/seed_forum_posts.py --force
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.forum import repository  # noqa: E402


def _lookup_team(pattern, season=None):
    if season is not None:
        hit = repository.find_team_and_match_by_name(pattern, season)
        if hit:
            return hit
    return repository.find_team_and_match_by_name(pattern) or {}


def build_starter_posts():
    now = datetime.now(timezone.utc)

    fnatic = _lookup_team("%fnatic%", 2024)
    geng = _lookup_team("%gen.g%", 2024)
    sentinels = _lookup_team("%sentinels%", 2024)
    prx = _lookup_team("%paper rex%", 2024)
    loud = _lookup_team("%loud%", 2023)
    eg = _lookup_team("%evil geniuses%", 2023)
    drx = _lookup_team("%drx%", 2024)
    heretics = _lookup_team("%heretics%", 2024)
    edg = _lookup_team("%edward gaming%", 2024)
    lev = _lookup_team("%leviat%", 2024)
    g2 = _lookup_team("%g2%", 2025)
    liquid = _lookup_team("%liquid%", 2023)
    kc = _lookup_team("%karmine%", 2024)
    nrg = _lookup_team("%nrg%", 2024)

    return [
        {
            "title": "Welcome to the VCI Forums — Sharing Tactical Breakdowns & Matchup Notes",
            "category": "General",
            "author_name": "VCI_Admin",
            "season": None,
            "team_id": None,
            "match_id": None,
            "map_name": None,
            "agent_name": None,
            "tags": ["welcome", "guide", "scouting"],
            "body": (
                "Welcome to the **Valorant Competitive Intelligence (VCI) Forums**!\n\n"
                "Use this space for both **long-form tactical breakdowns / scouting briefs** and **quick matchup discussions**:\n"
                "- Use **Markdown** (`### headings`, `**bold**`, bullet lists) to format tactical write-ups cleanly.\n"
                "- Add comma-separated **tags** (e.g., `ascent, pistol-round, eco`) so others can find threads quickly via the search bar."
            ),
            "initial_comments": [
                {
                    "author_name": "CoachKhai",
                    "body": "Excited to use this alongside the Competitive Analysis round breakdown tab!",
                    "created_at": now - timedelta(days=6, hours=2),
                },
            ],
        },
        {
            "title": "Breaking Down Ascent Mid-Control & Omen One-Way Setups",
            "category": "Tactical Breakdown",
            "author_name": "CoachKhai",
            "season": fnatic.get("season") or 2024,
            "team_id": fnatic.get("team_id"),
            "match_id": fnatic.get("match_id"),
            "map_name": "Ascent",
            "agent_name": "omen",
            "tags": ["ascent", "omen", "mid-control", "defence"],
            "body": (
                "### Key Takeaway\n"
                "Defaulting into **Market / Tiles control** early in the round consistently forces attackers "
                "into predictable A-Main executes.\n\n"
                "#### Round-by-Round Observations\n"
                "- **Pistol & Anti-Eco:** Pairing an Omen paranoia with a quick Catwalk reclear denies tree splits.\n"
                "- **Gun Rounds:** Saving the second smoke for a late retake on A-Site improves post-plant conversion.\n"
                "- **Counter-Prep:** Teams that invest an early Sova dart at Tiles force the defender Omen to reposition "
                "before the 1:15 mark.\n\n"
                "Check the *Rounds & Economy* tab in **Competitive Analysis** to see how pistol conversions shift the first-half scoreline."
            ),
            "initial_comments": [
                {
                    "author_name": "VCTAnalyst_SG",
                    "body": "Great breakdown. Have you noticed teams switching to a deeper Market hold when opponents run double-initiator?",
                    "created_at": now - timedelta(days=5, hours=5),
                },
                {
                    "author_name": "CoachKhai",
                    "body": "Yes—against KAY/O + Sova, playing one-and-done inside Pizza with a flash support works much better than fighting Tiles directly.",
                    "created_at": now - timedelta(days=5, hours=3, minutes=20),
                },
                {
                    "author_name": "MidLurker",
                    "body": "The late A-Tree smoke timing also cuts off post-plant spam from Wine.",
                    "created_at": now - timedelta(days=4, hours=18),
                },
            ],
        },
        {
            "title": "Scouting Brief: Gen.G Pistol Conversion & Bonus Round Tendencies",
            "category": "Scouting Brief",
            "author_name": "TacticalDesk",
            "season": geng.get("season") or 2024,
            "team_id": geng.get("team_id"),
            "match_id": geng.get("match_id"),
            "map_name": "Haven",
            "agent_name": "jett",
            "tags": ["haven", "pistol-round", "economy", "scouting"],
            "body": (
                "### Opponent Summary\n"
                "When reviewing recent Haven series, **Gen.G's** Round 2 anti-eco discipline stands out. "
                "They rarely give up isolated 1v1 duels against Sheriff/Stinger buys.\n\n"
                "#### Preparation Checklist\n"
                "1. **Respect the Bonus Round:** Expect aggressive A-Short or C-Long info plays to pick up rifles.\n"
                "2. **Jett Operator Timings:** Watch for early C-Long peeks on defence when economy clears 20k+ team loadout.\n"
                "3. **Post-Plant Spacing:** Force utility early on C-Site before committing to a full retake."
            ),
            "initial_comments": [
                {
                    "author_name": "PacificWatcher",
                    "body": "Their Round 3 bonus win rate is what usually snowballs halves into 9-3 leads.",
                    "created_at": now - timedelta(days=4, hours=4),
                },
            ],
        },
        {
            "title": "Matchup Discussion: Sentinels vs Structured Pacific Tempo",
            "category": "Matchup Discussion",
            "author_name": "RiftCaller",
            "season": sentinels.get("season") or 2024,
            "team_id": sentinels.get("team_id"),
            "match_id": sentinels.get("match_id"),
            "map_name": "Split",
            "agent_name": "raze",
            "tags": ["split", "raze", "tempo", "matchup"],
            "body": (
                "How do you think **Sentinels'** mid-round calling holds up against faster Pacific execute styles on Split?\n\n"
                "Looking at the scoreboards in **Teams / Players / Matches**, Sentinels thrive when they can slow down "
                "B-Heaven control and trade efficiently, whereas high-tempo Raze comps try to overwhelm Ramps before rotations arrive.\n\n"
                "Drop your thoughts below—which map veto order gives either side the cleanest path in a Bo3?"
            ),
            "initial_comments": [
                {
                    "author_name": "StratBook",
                    "body": "If Split stays in as Map 1, whoever wins defence pistol usually dictates the entire pace of the series.",
                    "created_at": now - timedelta(days=3, hours=12),
                },
                {
                    "author_name": "DualDuelist",
                    "body": "Agreed. Also worth watching how often teams still prioritize Viper on Split after recent utility adjustments.",
                    "created_at": now - timedelta(days=3, hours=9),
                },
            ],
        },
        {
            "title": "Agent & Map Meta: Is Double-Duelist Still Viable on Lotus?",
            "category": "Agent & Map Meta",
            "author_name": "MetaLab",
            "season": prx.get("season") or 2024,
            "team_id": prx.get("team_id"),
            "match_id": prx.get("match_id"),
            "map_name": "Lotus",
            "agent_name": "raze",
            "tags": ["lotus", "meta", "double-duelist", "compositions"],
            "body": (
                "### Meta Observation\n"
                "Across recent VCT seasons, Lotus has shifted heavily toward **A-Rubble fights** in the first 15 seconds.\n\n"
                "- **Double-Duelist (e.g., Raze + Neon/Jett):** Explosive A-Main contesting and fast C-Site floods, "
                "but leaves defence thin if the lone Sentinel gets picked early.\n"
                "- **Double-Controller (Omen + Viper):** Slower, methodical defaults that punish over-rotations through the revolving doors.\n\n"
                "Which composition do you prefer when prepping for a tournament bracket?"
            ),
            "initial_comments": [
                {
                    "author_name": "W_GamingFan",
                    "body": "Double duelist works as long as the Initiator (Fade or Breach) times utility cleanly for A-Rubble control.",
                    "created_at": now - timedelta(days=3, hours=2),
                },
            ],
        },
        {
            "title": "Bind B-Long & Hookah Crunch: Viper + Brimstone Post-Plant Protocols",
            "category": "Tactical Breakdown",
            "author_name": "SmokeLineup",
            "season": loud.get("season") or 2023,
            "team_id": loud.get("team_id"),
            "match_id": loud.get("match_id"),
            "map_name": "Bind",
            "agent_name": "viper",
            "tags": ["bind", "viper", "brimstone", "post-plant"],
            "body": (
                "### Attack Execute Blueprint\n"
                "Double-controller compositions on **Bind** remain one of the hardest setups to retake against once the spike goes down default on B.\n\n"
                "- **Wall Placement:** Cutting B-Elbow and CT Hallway simultaneously forces defenders to burn flashes before clearing Back-Site.\n"
                "- **Teleporter Fakes:** Dropping noise in A-Bath teleporter at 0:45 pulls the B-Garden anchor just long enough for a silent Hookah drop."
            ),
            "initial_comments": [
                {
                    "author_name": "AnchorMain",
                    "body": "Playing a judge inside Tube with a Viper orb is still the cleanest counter-stop on anti-ecos.",
                    "created_at": now - timedelta(days=2, hours=20),
                },
            ],
        },
        {
            "title": "Scouting Brief: Evil Geniuses Fracture Pinch Timings & Breach Stuns",
            "category": "Scouting Brief",
            "author_name": "VCTAnalyst_SG",
            "season": eg.get("season") or 2023,
            "team_id": eg.get("team_id"),
            "match_id": eg.get("match_id"),
            "map_name": "Fracture",
            "agent_name": "breach",
            "tags": ["fracture", "breach", "pinch", "scouting"],
            "body": (
                "### Key Tendencies\n"
                "On **Fracture**, disciplined teams rarely hit A-Main or B-Main single-lane without Dish or Arcade pressure.\n\n"
                "1. **Fault Line Opening:** Early stun down A-Hall forces defenders off Sands before the Raze satchel entry.\n"
                "2. **Retake Discipline:** Rather than fighting 2v3 on B-Site, defenders give up space and wait for Breach Rolling Thunder from Canteen."
            ),
            "initial_comments": [],
        },
        {
            "title": "Sunset Mid-Tiles Control: Cypher Trip Setups vs Neon Overdrive",
            "category": "Agent & Map Meta",
            "author_name": "SentinelWatch",
            "season": heretics.get("season") or 2024,
            "team_id": heretics.get("team_id"),
            "match_id": heretics.get("match_id"),
            "map_name": "Sunset",
            "agent_name": "cypher",
            "tags": ["sunset", "cypher", "neon", "sentinel"],
            "body": (
                "With **Neon** surge plays dominating B-Main and Market splits on **Sunset**, Cypher's unbreakable tripwires in B-Main "
                "have become mandatory.\n\n"
                "- **Anti-Sova Adjustments:** Vary trip height between ankle-level and crouch-head height so shock darts cannot reliably clear both.\n"
                "- **Camera Placement:** High B-Boba cam spots early Market lurks without exposing Cypher to Mid-Top spam."
            ),
            "initial_comments": [
                {
                    "author_name": "TechPause",
                    "body": "Pairing Cypher cage one-ways with Omen paranoia at B-Main completely stalls fast executes.",
                    "created_at": now - timedelta(days=2, hours=10),
                },
                {
                    "author_name": "SentinelWatch",
                    "body": "100%—and it preserves the rotating initiator's utility for the A-Site retake.",
                    "created_at": now - timedelta(days=2, hours=7),
                },
            ],
        },
        {
            "title": "Matchup Discussion: EDward Gaming Aggression vs EMEA Defaulting",
            "category": "Matchup Discussion",
            "author_name": "GlobalScouter",
            "season": edg.get("season") or 2024,
            "team_id": edg.get("team_id"),
            "match_id": edg.get("match_id"),
            "map_name": "Haven",
            "agent_name": "iso",
            "tags": ["haven", "iso", "aggression", "matchup"],
            "body": (
                "When **EDward Gaming** runs high-confidence aim-duel compositions (Iso / Jett / Neon), opponents often get caught "
                "holding passive angles.\n\n"
                "Do you think early info-gathering (Sova recon + Cypher cam) or proactive counter-aggression in A-Lobby works better against them?"
            ),
            "initial_comments": [
                {
                    "author_name": "RiftCaller",
                    "body": "Double-swinging A-Lobby with a flash on round start breaks their rhythm early.",
                    "created_at": now - timedelta(days=2, hours=3),
                },
            ],
        },
        {
            "title": "Icebox A-Site Retakes: Killjoy Lockdown Placement & Sova Lineups",
            "category": "Tactical Breakdown",
            "author_name": "FrostBite",
            "season": drx.get("season") or 2024,
            "team_id": drx.get("team_id"),
            "match_id": drx.get("match_id"),
            "map_name": "Icebox",
            "agent_name": "killjoy",
            "tags": ["icebox", "killjoy", "sova", "retake"],
            "body": (
                "### Retake Sequencing on Icebox\n"
                "Because **Icebox** features vertical ziplines and tight choke points around Pipes and Screens, disorganized retakes fail quickly.\n\n"
                "- **Lockdown Spot:** Placing Killjoy ultimate tucked behind **A-Screens** covers Default and 410 plants while staying safe from Rafters wallbangs.\n"
                "- **Viper Orb Deny:** Smoking off Belt forces attackers to drop down into crossfires if they try to delay defuse."
            ),
            "initial_comments": [],
        },
        {
            "title": "Scouting Brief: Leviatán Defence Side Win Rates & Eco Conversions",
            "category": "Scouting Brief",
            "author_name": "AmericasDesk",
            "season": lev.get("season") or 2024,
            "team_id": lev.get("team_id"),
            "match_id": lev.get("match_id"),
            "map_name": "Ascent",
            "agent_name": "sova",
            "tags": ["ascent", "sova", "defence", "economy"],
            "body": (
                "### Statistical Highlights\n"
                "Reviewing **Leviatán's** Ascent games in Competitive Analysis shows an unusually high **Thrifty / Half-Buy conversion rate** on defence.\n\n"
                "1. **Close-Range Stacks:** On eco rounds, they frequently stack 3 players in A-Tree / Garden with Classic right-clicks and Stingers.\n"
                "2. **Drone Discipline:** Attackers must clear Close-Left A-Main and Wine with a Sova Owl Drone before committing spike."
            ),
            "initial_comments": [
                {
                    "author_name": "EcoWatcher",
                    "body": "Their Sheriff-only buy discipline on Round 2 after a pistol loss keeps their Round 3 full-buy intact.",
                    "created_at": now - timedelta(days=1, hours=19),
                },
            ],
        },
        {
            "title": "Agent & Map Meta: Clove vs Omen as Solo Controller on Breeze & Sunset",
            "category": "Agent & Map Meta",
            "author_name": "ControllerMain",
            "season": g2.get("season") or 2025,
            "team_id": g2.get("team_id"),
            "match_id": g2.get("match_id"),
            "map_name": "Sunset",
            "agent_name": "clove",
            "tags": ["clove", "omen", "controller", "meta"],
            "body": (
                "### Choosing Your Solo Smoker\n"
                "Teams experimenting with **Clove** gain post-death smoke utility and self-heal snowball potential, "
                "but give up **Omen's Paranoia**—arguably the strongest retake flash in the game.\n\n"
                "- **Pick Clove** when running a heavy skirmish comp that takes early Mid/Tiles duels.\n"
                "- **Pick Omen** when your team relies on structured site executes and vertical off-angles."
            ),
            "initial_comments": [
                {
                    "author_name": "MetaLab",
                    "body": "Post-death smokes in 2v2 post-plants have won so many clutch rounds on Sunset B-Site.",
                    "created_at": now - timedelta(days=1, hours=14),
                },
            ],
        },
        {
            "title": "Breeze Mid-Doors & Halls Control: Countering Double-Initiator Info",
            "category": "Tactical Breakdown",
            "author_name": "DesertStrat",
            "season": liquid.get("season") or 2023,
            "team_id": liquid.get("team_id"),
            "match_id": liquid.get("match_id"),
            "map_name": "Breeze",
            "agent_name": "viper",
            "tags": ["breeze", "viper", "mid-control", "halls"],
            "body": (
                "### Holding Huge Sightlines\n"
                "On **Breeze**, losing Mid-Nest control splits the defence in half and makes rotating between A-Pyramids and B-Tunnel treacherous.\n\n"
                "- **Viper Fuel Management:** Toggle the Mid-Doors orb only when Sova recon or Skye flashes are heard—never burn full fuel at 1:40.\n"
                "- **Halls Presence:** Periodic jiggle peeks from A-Bridge prevent lurkers from walking uncontested into Defender Spawn."
            ),
            "initial_comments": [],
        },
        {
            "title": "Matchup Discussion: Karmine Corp vs Fnatic — Map Veto & Ban Priorities",
            "category": "Matchup Discussion",
            "author_name": "EMEAWatcher",
            "season": kc.get("season") or 2024,
            "team_id": kc.get("team_id"),
            "match_id": kc.get("match_id"),
            "map_name": "Lotus",
            "agent_name": "fade",
            "tags": ["lotus", "fade", "veto", "emea"],
            "body": (
                "In an EMEA Best-of-3 between **Karmine Corp** and **Fnatic**, Lotus and Ascent always sit at the center of the veto.\n\n"
                "If you're coaching Karmine Corp, do you float Lotus as Map 1 pick to test Fnatic's A-Rubble protocol, or ban it outright and force Haven?"
            ),
            "initial_comments": [
                {
                    "author_name": "StratBook",
                    "body": "Banning Lotus and picking Sunset forces Fnatic onto a much tighter map pool.",
                    "created_at": now - timedelta(days=1, hours=6),
                },
            ],
        },
        {
            "title": "Scouting Brief: NRG Attack-Side Defaults & Late-Round Executions",
            "category": "Scouting Brief",
            "author_name": "TacticalDesk",
            "season": nrg.get("season") or 2024,
            "team_id": nrg.get("team_id"),
            "match_id": nrg.get("match_id"),
            "map_name": "Bind",
            "agent_name": "skye",
            "tags": ["bind", "skye", "default", "scouting"],
            "body": (
                "### Clock Management Breakdown\n"
                "**NRG** consistently drains defender utility across A-Short and B-Long before committing to an execute under **0:25 remaining**.\n\n"
                "1. **Hold Counter-Smokes:** Defenders who drop both smokes on the first fake at 1:10 are left dry for the real hit.\n"
                "2. **Skye Dog Timings:** Watch for the Trailblazer clearing U-Hall at 0:35—that usually signals an A-Site commit."
            ),
            "initial_comments": [],
        },
        {
            "title": "Agent & Map Meta: Gekko Wingman Plant Metas on Sunset & Lotus",
            "category": "Agent & Map Meta",
            "author_name": "UtilityLab",
            "season": prx.get("season") or 2024,
            "team_id": prx.get("team_id"),
            "match_id": prx.get("match_id"),
            "map_name": "Sunset",
            "agent_name": "gekko",
            "tags": ["gekko", "sunset", "lotus", "initiator"],
            "body": (
                "### Why Gekko Replaced Skye on Tight Sites\n"
                "Sending **Wingman** to plant while all five attackers hold post-plant crossfires completely changes risk math on **Sunset B-Site** and **Lotus C-Site**.\n\n"
                "- **Orb Economy:** Reclaiming Dizzy and Wingman after a site take gives attackers a second wave of flashes for post-plant stall.\n"
                "- **Counterplay:** Defenders must prioritize shooting Wingman over peeking the entry duelist."
            ),
            "initial_comments": [
                {
                    "author_name": "VCTAnalyst_SG",
                    "body": "Plus Wingman defusing in 1v1 clutches forces the defender to swing out of post-plant cover.",
                    "created_at": now - timedelta(hours=16),
                },
            ],
        },
        {
            "title": "Pearl B-Ramp Post-Plant Spam & Harbour Cove Plant Setups",
            "category": "Tactical Breakdown",
            "author_name": "WaveCaller",
            "season": loud.get("season") or 2023,
            "team_id": loud.get("team_id"),
            "match_id": loud.get("match_id"),
            "map_name": "Pearl",
            "agent_name": "viper",
            "tags": ["pearl", "viper", "b-site", "post-plant"],
            "body": (
                "### Classic B-Long Execute\n"
                "Before **Pearl** rotated out of the active pool, B-Long executes defined the meta:\n\n"
                "- **Viper Wall + Cove:** Cutting B-Link and B-Tower allowed an almost uncontestable B-Long edge plant.\n"
                "- **Post-Plant:** Playing 4 players down B-Long with Viper snakebites and Sova shock darts made defusing nearly impossible without smoke cover."
            ),
            "initial_comments": [],
        },
        {
            "title": "How to Interpret Round Economy & ACS Metrics When Scouting Opponents",
            "category": "General",
            "author_name": "VCI_Admin",
            "season": None,
            "team_id": None,
            "match_id": None,
            "map_name": None,
            "agent_name": None,
            "tags": ["guide", "analytics", "acs", "economy"],
            "body": (
                "### Quick Analytics Reminder\n"
                "When preparing scouting briefs from the **Teams / Players / Matches** and **Competitive Analysis** tabs, keep these dataset nuances in mind:\n\n"
                "- **Match Series vs Map Games:** A Best-of-3 series has 1 `match_id` and up to 3 `game_id` map records.\n"
                "- **Pistol & Bonus Denominators:** Only recorded pistol rounds with a recorded following round are counted in conversion rates.\n"
                "- **Small Sample Caution:** A 100% map win rate across 1–2 games is a starting point for VOD review, not a guaranteed veto ban."
            ),
            "initial_comments": [
                {
                    "author_name": "TacticalDesk",
                    "body": "Pinned-worthy reminder—always check map game counts before drawing conclusions from win percentages.",
                    "created_at": now - timedelta(hours=6),
                },
            ],
        },
    ]


def _get_existing_counts():
    pg_count = repository.count_posts()
    client, collection = repository.get_mongo_collection()
    try:
        mongo_count = collection.count_documents({})
    finally:
        client.close()
    return pg_count, mongo_count


def main():
    parser = argparse.ArgumentParser(description="Populate VCT starter forum threads.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Insert starter threads even if forum_posts / forum_threads already contain records.",
    )
    args = parser.parse_args()

    pg_count, mongo_count = _get_existing_counts()
    if (pg_count > 0 or mongo_count > 0) and not args.force:
        print(
            f"Forum is not empty (PostgreSQL forum_posts={pg_count}, MongoDB forum_threads={mongo_count}). "
            "Skipping seed. Run `python scripts/clear_forum_posts.py` first or pass `--force`."
        )
        return

    posts = build_starter_posts()
    for idx, post in enumerate(posts, start=1):
        post_id = repository.create_post(**post)
        print(f"[{idx}/{len(posts)}] Inserted post #{post_id}: {post['title']}")

    print(f"\nSuccessfully seeded {len(posts)} forum threads into PostgreSQL and MongoDB.")


if __name__ == "__main__":
    main()