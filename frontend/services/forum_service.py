"""Frontend adapter for the Forums tab (PostgreSQL + MongoDB CRUD)."""

from backend.forum import service as backend

CATEGORIES = backend.CATEGORIES


class DataServiceError(Exception):
    """Raised when forum data cannot be loaded or saved."""


def list_posts(search="", category="", sort_by="Newest first"):
    try:
        return backend.list_posts(
            search=search,
            category=category,
            sort_by=sort_by,
        )
    except Exception as error:
        raise DataServiceError("Forum posts could not be loaded.") from error


def get_post(post_id):
    try:
        return backend.get_post(post_id)
    except Exception as error:
        raise DataServiceError("Forum thread could not be loaded.") from error


def create_post(title, category, author_name, body, tags_input=""):
    try:
        return backend.create_post(
            title=title,
            category=category,
            author_name=author_name,
            body=body,
            tags_input=tags_input,
        )
    except ValueError:
        raise
    except Exception as error:
        raise DataServiceError("Post could not be created.") from error


def update_post(post_id, title, category, author_name, body, tags_input=""):
    try:
        backend.update_post(
            post_id=post_id,
            title=title,
            category=category,
            author_name=author_name,
            body=body,
            tags_input=tags_input,
        )
    except ValueError:
        raise
    except Exception as error:
        raise DataServiceError("Post could not be updated.") from error


def delete_post(post_id):
    try:
        backend.delete_post(post_id)
    except Exception as error:
        raise DataServiceError("Post could not be deleted.") from error


def add_comment(post_id, author_name, body):
    try:
        return backend.add_comment(post_id, author_name, body)
    except ValueError:
        raise
    except Exception as error:
        raise DataServiceError("Comment could not be added.") from error


def update_comment(post_id, comment_id, body):
    try:
        backend.update_comment(post_id, comment_id, body)
    except ValueError:
        raise
    except Exception as error:
        raise DataServiceError("Comment could not be updated.") from error


def delete_comment(post_id, comment_id):
    try:
        backend.delete_comment(post_id, comment_id)
    except Exception as error:
        raise DataServiceError("Comment could not be deleted.") from error