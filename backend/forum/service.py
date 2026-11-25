"""Service layer for the Forums feature (PostgreSQL + MongoDB)."""

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


def list_posts(search="", category="", sort_by="Newest first"):
    """Return filtered and sorted forum posts."""
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