"""Service layer for the Forums feature (PostgreSQL + MongoDB)."""

from . import repository

CATEGORIES = repository.CATEGORIES
PINNED_TAG = "pinned"


def _parse_tags_input(raw_tags):
    if isinstance(raw_tags, (list, tuple)):
        items = raw_tags
    else:
        items = str(raw_tags or "").split(",")
    return [t for t in repository._normalize_tags(items) if t != PINNED_TAG]


def _enrich_post(post):
    if not post:
        return None
    raw_tags = post.get("tags") or []
    post["is_pinned"] = PINNED_TAG in raw_tags
    post["display_tags"] = [t for t in raw_tags if t != PINNED_TAG]
    return post


def _validate_post_fields(title, category, author_name, body):
    if not str(title or "").strip():
        raise ValueError("Title is required.")
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")
    if not str(author_name or "").strip():
        raise ValueError("Author display name is required.")
    if not str(body or "").strip():
        raise ValueError("Post body is required.")


def list_posts(search="", category="", sort_by="Newest first"):
    """Return filtered and sorted forum posts, keeping pinned posts at the top."""
    all_posts = [_enrich_post(p) for p in repository.fetch_all_posts()]

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
                    " ".join(post.get("display_tags") or []),
                ]
            ).casefold()
            if term not in haystack:
                continue
        filtered.append(post)

    if sort_by == "Most commented":
        filtered.sort(
            key=lambda p: (
                not p["is_pinned"],
                -p["comment_count"],
                -(p["created_at"].timestamp() if p.get("created_at") else 0),
                -p["post_id"],
            )
        )
    else:
        filtered.sort(
            key=lambda p: (
                p["is_pinned"],
                p["created_at"].timestamp() if p.get("created_at") else 0,
                p["post_id"],
            ),
            reverse=True,
        )

    return {
        "posts": filtered,
        "total_posts": len(all_posts),
        "categories": list(CATEGORIES),
    }


def get_post(post_id):
    return _enrich_post(repository.fetch_post_by_id(post_id))


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
    existing = get_post(post_id)
    if not existing:
        raise ValueError(f"Post #{int(post_id)} was not found.")

    tags = _parse_tags_input(tags_input)
    if existing["is_pinned"]:
        tags = [PINNED_TAG, *tags]

    repository.update_post(
        post_id=post_id,
        title=title,
        category=category,
        author_name=author_name,
        body=body,
        tags=tags,
    )


def toggle_pin(post_id):
    """Toggle the reserved 'pinned' tag in MongoDB without altering DB schemas."""
    post = get_post(post_id)
    if not post:
        raise ValueError(f"Post #{int(post_id)} was not found.")

    pid = int(post_id)
    client, collection = repository.get_mongo_collection()
    try:
        if post["is_pinned"]:
            collection.update_one(
                {"post_id": pid},
                {"$pull": {"tags": PINNED_TAG}},
            )
            return False
        collection.update_one(
            {"post_id": pid},
            {
                "$addToSet": {"tags": PINNED_TAG},
                "$setOnInsert": {"comments": []},
            },
            upsert=True,
        )
        return True
    finally:
        client.close()


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