"""Service layer for the Forums feature (PostgreSQL + MongoDB)."""

from datetime import datetime, timedelta, timezone
from . import repository

CATEGORIES = repository.CATEGORIES


def _parse_tags_input(raw_tags):
    if isinstance(raw_tags, (list, tuple)):
        items = raw_tags
    else:
        items = str(raw_tags or "").split(",")
    return repository._normalize_tags(items)


def _validate_post_fields(title, category, author_name, body):
    if not str(title or "").strip():
        raise ValueError("Title is required.")
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if not str(author_name or "").strip():
        raise ValueError("Author display name is required.")
    if not str(body or "").strip():
        raise ValueError("Post body is required.")


def ensure_seeded():
    """Idempotently seed 5 domain-authentic starter posts if forum_posts is empty."""
    if repository.count_posts() > 0:
        return False

    now = datetime.now(timezone.utc)

    fnatic = repository.find_team_and_match_by_name("%fnatic%", 2024) or repository.find_team_and_match_by_name("%fnatic%")
    geng = repository.find_team_and_match_by_name("%gen.g%", 2024) or repository.find_team_and_match_by_name("%gen.g%")
    sentinels = repository.find_team_and_match_by_name("%sentinels%", 2024) or repository.find_team_and_match_by_name("%sentinels%")
    prx = repository.find_team_and_match_by_name("%paper rex%", 2024) or repository.find_team_and_match_by_name("%paper rex%")

    starter_posts = [
        {
            "title": "Breaking Down Ascent Mid-Control & Omen One-Way Setups",
            "category": "Tactical Breakdown",
            "author_name": "CoachKhai",
            "season": (fnatic or {}).get("season") or 2024,
            "team_id": (fnatic or {}).get("team_id"),
            "match_id": (fnatic or {}).get("match_id"),
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
                    "created_at": now - timedelta(hours=5),
                },
                {
                    "author_name": "CoachKhai",
                    "body": "Yes—against KAY/O + Sova, playing one-and-done inside Pizza with a flash support works much better than fighting Tiles directly.",
                    "created_at": now - timedelta(hours=3, minutes=20),
                },
            ],
        },
        {
            "title": "Scouting Brief: Gen.G Pistol Conversion & Bonus Round Tendencies",
            "category": "Scouting Brief",
            "author_name": "TacticalDesk",
            "season": (geng or {}).get("season") or 2024,
            "team_id": (geng or {}).get("team_id"),
            "match_id": (geng or {}).get("match_id"),
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
                    "created_at": now - timedelta(hours=4),
                },
            ],
        },
        {
            "title": "Matchup Discussion: Sentinels vs Structured Pacific Tempo",
            "category": "Matchup Discussion",
            "author_name": "RiftCaller",
            "season": (sentinels or {}).get("season") or 2024,
            "team_id": (sentinels or {}).get("team_id"),
            "match_id": (sentinels or {}).get("match_id"),
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
                    "created_at": now - timedelta(hours=2, minutes=45),
                },
                {
                    "author_name": "DualDuelist",
                    "body": "Agreed. Also worth watching how often teams still prioritize Viper on Split after recent utility adjustments.",
                    "created_at": now - timedelta(hours=1, minutes=30),
                },
            ],
        },
        {
            "title": "Agent & Map Meta: Is Double-Duelist Still Viable on Lotus?",
            "category": "Agent & Map Meta",
            "author_name": "MetaLab",
            "season": (prx or {}).get("season") or 2024,
            "team_id": (prx or {}).get("team_id"),
            "match_id": (prx or {}).get("match_id"),
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
                    "created_at": now - timedelta(minutes=50),
                },
            ],
        },
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
            "initial_comments": [],
        },
    ]

    for post in starter_posts:
        repository.create_post(**post)
    return True


def list_posts(search="", category="", sort_by="Newest first"):
    """Return filtered and sorted forum posts."""
    ensure_seeded()
    all_posts = repository.fetch_all_posts()

    term = (search or "").strip().casefold()
    filtered = []
    for post in all_posts:
        if category and post["category"] != category:
            continue
        if term:
            haystack = " ".join(
                [
                    post.get("title") or "",
                    post.get("body") or "",
                    post.get("author_name") or "",
                    post.get("team_name") or "",
                    post.get("map_name") or "",
                    post.get("agent_name") or "",
                    " ".join(post.get("tags") or []),
                ]
            ).casefold()
            if term not in haystack:
                continue
        filtered.append(post)

    if sort_by == "Most commented":
        filtered.sort(
            key=lambda p: (-p["comment_count"], -(p["created_at"].timestamp() if p.get("created_at") else 0))
        )
    else:
        filtered.sort(
            key=lambda p: (p["created_at"].timestamp() if p.get("created_at") else 0, p["post_id"]),
            reverse=True,
        )

    return {
        "posts": filtered,
        "total_posts": len(all_posts),
        "categories": list(CATEGORIES),
    }


def get_post(post_id):
    return repository.fetch_post_by_id(post_id)


def create_post(title, category, author_name, body, tags_input=""):
    _validate_post_fields(title, category, author_name, body)
    tags = _parse_tags_input(tags_input)
    return repository.create_post(
        title=title,
        category=category,
        author_name=author_name,
        body=body,
        tags=tags,
    )


def update_post(post_id, title, category, author_name, body, tags_input=""):
    _validate_post_fields(title, category, author_name, body)
    tags = _parse_tags_input(tags_input)
    repository.update_post(
        post_id=post_id,
        title=title,
        category=category,
        author_name=author_name,
        body=body,
        tags=tags,
    )


def delete_post(post_id):
    repository.delete_post(post_id)


def add_comment(post_id, author_name, body):
    if not str(author_name or "").strip():
        raise ValueError("Author display name is required.")
    if not str(body or "").strip():
        raise ValueError("Comment body cannot be empty.")
    return repository.add_comment(post_id, author_name, body)


def update_comment(post_id, comment_id, body):
    if not str(body or "").strip():
        raise ValueError("Comment body cannot be empty.")
    repository.update_comment(post_id, comment_id, body)


def delete_comment(post_id, comment_id):
    repository.delete_comment(post_id, comment_id)