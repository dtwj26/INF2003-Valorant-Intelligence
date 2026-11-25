"""Forums view: tactical breakdowns and community discussions (PostgreSQL + MongoDB CRUD)."""

from datetime import datetime
from html import escape

import streamlit as st
import streamlit.components.v2 as components

from components.agent_names import format_agent_name
from components.asset_catalog import get_agent_image, get_map_image, get_team_logo
from services import forum_service as service

PAGE_SIZE = 5


_FORUM_DOM_GUARD = components.component(
    "forum_dom_guard",
    html='<div style="display:none;"></div>',
    isolate_styles=False,
    js="""export default function(component) {
        const doc = window.parent.document;

        function cleanInputHints() {
            const forumsRoot = doc.querySelector('.st-key-forums_page');
            if (!forumsRoot) return;
            forumsRoot.querySelectorAll('[data-testid="InputInstructions"]').forEach(el => {
                if (!el.closest('.st-key-forum_search_box')) {
                    el.remove();
                }
            });
        }

        cleanInputHints();

        if (!doc._vciForumObserverAttached) {
            doc._vciForumObserverAttached = true;
            const observer = new MutationObserver(cleanInputHints);
            observer.observe(doc.body, { childList: true, subtree: true });
        }

        if (!doc._vciForumEnterGuardAttached) {
            doc._vciForumEnterGuardAttached = true;
            doc.addEventListener('keydown', function(e) {
                if (e.key !== 'Enter') return;
                const target = e.target;
                if (!target) return;

                const forumsRoot = target.closest('.st-key-forums_page');
                if (!forumsRoot) return;

                if (target.tagName === 'TEXTAREA') return;

                if (target.tagName === 'INPUT' && target.closest('.st-key-forum_search_box')) return;

                if (target.tagName === 'INPUT') {
                    e.preventDefault();
                    e.stopPropagation();
                }
            }, true);
        }
    }""",
)


def _inject_forum_ui_enhancements():
    """Scope button/link colors to Forums, hide InputInstructions hints, and block Enter submission on post/comment inputs."""
    st.html(
        """
        <style>
        /* BLACK buttons: Close Editor, Open thread, Search, Back to forums, Edit Post, Cancel Edit, Edit Comment */
        .st-key-forums_page .st-key-forum_close_editor button,
        .st-key-forums_page .st-key-forum_close_editor button p,
        .st-key-forums_page [class*="st-key-open_forum_post_"] button,
        .st-key-forums_page [class*="st-key-open_forum_post_"] button p,
        .st-key-forums_page .st-key-forum_search_btn button,
        .st-key-forums_page .st-key-forum_search_btn button p,
        .st-key-forums_page .st-key-forum_back_btn button,
        .st-key-forums_page .st-key-forum_back_btn button p,
        .st-key-forums_page [class*="st-key-toggle_edit_post_"] button,
        .st-key-forums_page [class*="st-key-toggle_edit_post_"] button p,
        .st-key-forums_page [class*="st-key-edit_c_btn_"] button,
        .st-key-forums_page [class*="st-key-edit_c_btn_"] button p {
            background-color: #101821 !important;
            border-color: #101821 !important;
            color: #ffffff !important;
        }
        .st-key-forums_page .st-key-forum_close_editor button:hover,
        .st-key-forums_page [class*="st-key-open_forum_post_"] button:hover,
        .st-key-forums_page .st-key-forum_search_btn button:hover,
        .st-key-forums_page .st-key-forum_back_btn button:hover,
        .st-key-forums_page [class*="st-key-toggle_edit_post_"] button:hover,
        .st-key-forums_page [class*="st-key-edit_c_btn_"] button:hover {
            background-color: #1e293b !important;
            border-color: #1e293b !important;
            color: #ffffff !important;
        }

        /* GREEN buttons: New Post, Publish Post, Save Changes, Post Comment, Save Comment */
        .st-key-forums_page .st-key-forum_new_post button,
        .st-key-forums_page .st-key-forum_new_post button p,
        .st-key-forums_page .st-key-forum_create_submit button,
        .st-key-forums_page .st-key-forum_create_submit button p,
        .st-key-forums_page [class*="st-key-forum_edit_"][class*="_submit"] button,
        .st-key-forums_page [class*="st-key-forum_edit_"][class*="_submit"] button p,
        .st-key-forums_page [class*="st-key-submit_comment_btn_"] button,
        .st-key-forums_page [class*="st-key-submit_comment_btn_"] button p,
        .st-key-forums_page [class*="st-key-save_comment_btn_"] button,
        .st-key-forums_page [class*="st-key-save_comment_btn_"] button p {
            background-color: #15803d !important;
            border-color: #15803d !important;
            color: #ffffff !important;
        }
        .st-key-forums_page .st-key-forum_new_post button:hover,
        .st-key-forums_page .st-key-forum_create_submit button:hover,
        .st-key-forums_page [class*="st-key-forum_edit_"][class*="_submit"] button:hover,
        .st-key-forums_page [class*="st-key-submit_comment_btn_"] button:hover,
        .st-key-forums_page [class*="st-key-save_comment_btn_"] button:hover {
            background-color: #166534 !important;
            border-color: #166534 !important;
            color: #ffffff !important;
        }

        /* RED buttons: Delete Post, Confirm Delete, Delete Comment */
        .st-key-forums_page [class*="st-key-ask_delete_post_"] button,
        .st-key-forums_page [class*="st-key-ask_delete_post_"] button p,
        .st-key-forums_page [class*="st-key-confirm_del_post_"] button,
        .st-key-forums_page [class*="st-key-confirm_del_post_"] button p,
        .st-key-forums_page [class*="st-key-del_c_btn_"] button,
        .st-key-forums_page [class*="st-key-del_c_btn_"] button p {
            background-color: #b91c1c !important;
            border-color: #b91c1c !important;
            color: #ffffff !important;
        }
        .st-key-forums_page [class*="st-key-ask_delete_post_"] button:hover,
        .st-key-forums_page [class*="st-key-confirm_del_post_"] button:hover,
        .st-key-forums_page [class*="st-key-del_c_btn_"] button:hover {
            background-color: #991b1b !important;
            border-color: #991b1b !important;
            color: #ffffff !important;
        }

        /* Hide 'Press Enter to apply' / 'Press Ctrl+Enter to apply' hints on all Forums inputs except search bar */
        .st-key-forums_page [data-testid="InputInstructions"] {
            display: none !important;
        }
        .st-key-forums_page .st-key-forum_search_box [data-testid="InputInstructions"] {
            display: block !important;
        }

        /* Hyperlink style for 'Clear all filters' AND Pagination links (Previous / 1 2 3 / Next) */
        .st-key-forums_page .st-key-forum_clear_filters_btn {
            display: flex !important;
            justify-content: flex-end !important;
        }
        .st-key-forums_page .st-key-forum_clear_filters_btn button,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 2px 5px !important;
            min-height: 0 !important;
            width: auto !important;
            color: #b91c1c !important;
            text-decoration: underline !important;
            font-weight: 500 !important;
            cursor: pointer !important;
            transition: color 0.15s ease, transform 0.08s ease !important;
        }
        .st-key-forums_page .st-key-forum_clear_filters_btn button p,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button p {
            color: #b91c1c !important;
            text-decoration: underline !important;
            font-weight: 500 !important;
        }
        .st-key-forums_page .st-key-forum_clear_filters_btn button:hover,
        .st-key-forums_page .st-key-forum_clear_filters_btn button:hover p,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:not(:disabled):hover,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:not(:disabled):hover p {
            background: transparent !important;
            color: #991b1b !important;
            text-decoration-thickness: 2px !important;
        }
        .st-key-forums_page .st-key-forum_clear_filters_btn button:active,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:not(:disabled):active {
            background: transparent !important;
            color: #7f1d1d !important;
            transform: translateY(1px) !important;
        }
        .st-key-forums_page .st-key-forum_clear_filters_btn button:focus,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:focus {
            box-shadow: none !important;
            outline: none !important;
        }

        /* Disabled state for Previous / Next pagination links */
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:disabled,
        .st-key-forums_page [class*="st-key-forum_page_link_"] button:disabled p {
            color: #94a3b8 !important;
            text-decoration: none !important;
            cursor: not-allowed !important;
            opacity: 0.75 !important;
        }

        /* Active current page number in pagination */
        .st-key-forums_page .st-key-forum_page_link_active button:disabled,
        .st-key-forums_page .st-key-forum_page_link_active button:disabled p {
            color: #101821 !important;
            font-weight: 700 !important;
            text-decoration: underline !important;
            text-decoration-thickness: 2px !important;
            opacity: 1 !important;
            cursor: default !important;
        }

        /* Red grouped wrapper for Delete Post confirmation & buttons */
        .st-key-forums_page [class*="st-key-delete_post_group_"] {
            background-color: #fef2f2 !important;
            border: 1px solid #b91c1c !important;
            border-radius: 4px !important;
            padding: 12px 16px !important;
            margin: 8px 0 12px 0 !important;
        }
        .st-key-forums_page [class*="st-key-delete_post_group_"] p {
            color: #991b1b !important;
            font-weight: 500 !important;
        }
        .st-key-forums_page [class*="st-key-confirm_del_post_"] button,
        .st-key-forums_page [class*="st-key-confirm_del_post_"] button p {
            color: #ffffff !important;
        }
        .st-key-forums_page [class*="st-key-cancel_del_post_"] button,
        .st-key-forums_page [class*="st-key-cancel_del_post_"] button p {
            background-color: #ffffff !important;
            border-color: #b91c1c !important;
            color: #991b1b !important;
        }
        .st-key-forums_page [class*="st-key-cancel_del_post_"] button:hover,
        .st-key-forums_page [class*="st-key-cancel_del_post_"] button:hover p {
            background-color: #fee2e2 !important;
            border-color: #991b1b !important;
            color: #7f1d1d !important;
        }
        </style>
        """
    )

    _FORUM_DOM_GUARD(key="forum_dom_guard_v2")


def _format_timestamp(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value.strftime("%d %b %Y, %H:%M UTC")


def _asset_img(filename, size=20):
    if not filename:
        return ""
    return (
        f'<img src="app/static/{escape(filename, quote=True)}" alt="" '
        f'style="width:{size}px;height:{size}px;object-fit:cover;border-radius:2px;'
        f'vertical-align:middle;margin-right:6px;">'
    )


def _badge_html(label, bg="#eef2f6", color="#17212d", img_html=""):
    return (
        f'<span style="display:inline-flex;align-items:center;padding:3px 9px;'
        f'margin:2px 6px 2px 0;border-radius:2px;font-size:0.82rem;font-weight:500;'
        f'background:{bg};color:{color};border:1px solid #d7e0e8;">'
        f'{img_html}{escape(str(label))}</span>'
    )


def _render_entity_badges(post):
    badges = [_badge_html(post["category"], bg="#101821", color="#f1f4f7")]

    if post.get("season"):
        badges.append(_badge_html(f"Season {post['season']}"))

    if post.get("team_name"):
        team_img = _asset_img(get_team_logo(post.get("team_id")), size=16)
        badges.append(_badge_html(post["team_name"], img_html=team_img))

    if post.get("match_name"):
        label = f"Match #{post['match_id']}: {post['match_name']}"
        badges.append(_badge_html(label))

    if post.get("map_name"):
        map_img = _asset_img(get_map_image(post["map_name"]), size=16)
        badges.append(_badge_html(post["map_name"], img_html=map_img))

    if post.get("agent_name"):
        agent_display = format_agent_name(post["agent_name"])
        agent_img = _asset_img(get_agent_image(post["agent_name"]), size=16)
        badges.append(_badge_html(agent_display, img_html=agent_img))

    for tag in post.get("tags") or []:
        badges.append(_badge_html(f"#{tag}", bg="#f8fafc", color="#475569"))

    st.html('<div style="display:flex;flex-wrap:wrap;align-items:center;margin:6px 0 10px 0;">' + "".join(badges) + "</div>")


def _open_post(post_id):
    st.session_state.forum_selected_post_id = int(post_id)
    st.session_state.forum_editing_post = False
    st.session_state.forum_editing_comment_id = None
    st.session_state.forum_confirm_delete_post = False


def _back_to_list():
    st.session_state.forum_selected_post_id = None
    st.session_state.forum_editing_post = False
    st.session_state.forum_editing_comment_id = None
    st.session_state.forum_confirm_delete_post = False


def _render_post_form(mode="create", post=None):
    """Simplified form for creating or editing a forum post (button click required)."""
    prefix = "forum_create" if mode == "create" else f"forum_edit_{post['post_id']}"
    submit_label = "Publish Post" if mode == "create" else "Save Changes"

    default_title = post["title"] if post else ""
    default_category = post["category"] if post else service.CATEGORIES[0]
    default_author = post["author_name"] if post else ""
    default_tags = ", ".join(post.get("tags") or []) if post else ""
    default_body = post["body"] if post else ""

    title = st.text_input(
        "Title *",
        value=default_title,
        placeholder="e.g., Ascent Mid-Control Breakdown",
        key=f"{prefix}_title",
    )

    col1, col2 = st.columns([1, 1], gap="medium")
    with col1:
        cat_idx = list(service.CATEGORIES).index(default_category) if default_category in service.CATEGORIES else 0
        category = st.selectbox(
            "Category *",
            list(service.CATEGORIES),
            index=cat_idx,
            key=f"{prefix}_category",
        )
    with col2:
        author_name = st.text_input(
            "Author Display Name *",
            value=default_author,
            placeholder="Your name or handle",
            key=f"{prefix}_author",
        )

    tags_input = st.text_input(
        "Tags (comma-separated, optional)",
        value=default_tags,
        placeholder="e.g., ascent, omen, pistol-round",
        key=f"{prefix}_tags",
    )

    body = st.text_area(
        "Body (Markdown supported) *",
        value=default_body,
        height=220,
        placeholder="Write your tactical breakdown, scouting notes, or matchup discussion using Markdown...",
        key=f"{prefix}_body",
    )

    btn_col1, _ = st.columns([1, 4])
    if btn_col1.button(submit_label, type="primary", width="stretch", key=f"{prefix}_submit"):
        try:
            if mode == "create":
                new_id = service.create_post(
                    title=title,
                    category=category,
                    author_name=author_name,
                    body=body,
                    tags_input=tags_input,
                )
                st.session_state.forum_show_create = False
                for suffix in ("title", "category", "author", "tags", "body"):
                    st.session_state.pop(f"{prefix}_{suffix}", None)
                _open_post(new_id)
                st.rerun()
            else:
                service.update_post(
                    post_id=post["post_id"],
                    title=title,
                    category=category,
                    author_name=author_name,
                    body=body,
                    tags_input=tags_input,
                )
                st.session_state.forum_editing_post = False
                for suffix in ("title", "category", "author", "tags", "body"):
                    st.session_state.pop(f"{prefix}_{suffix}", None)
                st.rerun()
        except ValueError as err:
            st.warning(str(err))
        except service.DataServiceError as err:
            st.error(str(err))


def _render_detail(post_id):
    st.button("Back to forums", on_click=_back_to_list, key="forum_back_btn")

    try:
        post = service.get_post(post_id)
    except service.DataServiceError as err:
        st.error(str(err))
        return

    if not post:
        st.warning("This thread could not be found. It may have been deleted.")
        return

    # Header & Actions
    head_col, action_col = st.columns([3.5, 1.5], vertical_alignment="top")
    with head_col:
        st.subheader(post["title"])
        meta = f"Posted by **{post['author_name']}** · {_format_timestamp(post['created_at'])}"
        if post.get("updated_at") and post["updated_at"] != post["created_at"]:
            meta += f" · Edited {_format_timestamp(post['updated_at'])}"
        st.caption(meta)
    with action_col:
        b1, b2 = st.columns(2)
        if b1.button(
            "Cancel Edit" if st.session_state.get("forum_editing_post") else "Edit Post",
            key=f"toggle_edit_post_{post_id}",
            width="stretch",
        ):
            st.session_state.forum_editing_post = not st.session_state.get("forum_editing_post", False)
            st.session_state.forum_confirm_delete_post = False
            st.rerun()
        if b2.button("Delete Post", key=f"ask_delete_post_{post_id}", width="stretch"):
            st.session_state.forum_confirm_delete_post = True
            st.session_state.forum_editing_post = False
            st.rerun()

    # Grouped Red Delete Confirmation Box
    if st.session_state.get("forum_confirm_delete_post"):
        with st.container(key=f"delete_post_group_{post_id}"):
            st.markdown("Delete this thread permanently from both PostgreSQL and MongoDB?")
            c1, c2, _ = st.columns([1.2, 1, 3.8])
            if c1.button("Confirm Delete", type="primary", key=f"confirm_del_post_{post_id}", width="stretch"):
                try:
                    service.delete_post(post_id)
                    _back_to_list()
                    st.rerun()
                except service.DataServiceError as err:
                    st.error(str(err))
            if c2.button("Cancel", key=f"cancel_del_post_{post_id}", width="stretch"):
                st.session_state.forum_confirm_delete_post = False
                st.rerun()

    # Inline Edit Form or Rendered Post Content
    if st.session_state.get("forum_editing_post"):
        st.divider()
        st.markdown("#### Edit Post")
        _render_post_form(mode="edit", post=post)
        return

    _render_entity_badges(post)

    with st.container(border=True):
        st.markdown(post["body"])

    # Flat Comments Section (MongoDB)
    st.divider()
    comments = post.get("comments") or []
    st.markdown(f"### Comments ({len(comments)})")
    st.caption("Flat chronological discussion stored in MongoDB (`valorant_intelligence.forum_threads`).")

    if not comments:
        st.info("No comments yet. Start the discussion below.")
    else:
        for comment in comments:
            cid = comment["comment_id"]
            with st.container(border=True):
                c_head, c_actions = st.columns([3.4, 1.9], vertical_alignment="center")
                ts = _format_timestamp(comment.get("created_at"))
                edited = (
                    comment.get("updated_at")
                    and comment.get("created_at")
                    and comment["updated_at"] != comment["created_at"]
                )
                c_head.markdown(
                    f"<strong>{escape(comment['author_name'])}</strong> "
                    f"<span style='color:#64748b;font-size:0.85rem;'>· {escape(ts)}"
                    f"{' (edited)' if edited else ''}</span>",
                    unsafe_allow_html=True,
                )
                eb, db = c_actions.columns(2)
                is_editing = st.session_state.get("forum_editing_comment_id") == cid
                if eb.button("Cancel" if is_editing else "Edit Comment", key=f"edit_c_btn_{cid}", width="stretch"):
                    st.session_state.forum_editing_comment_id = None if is_editing else cid
                    st.rerun()
                if db.button("Delete Comment", key=f"del_c_btn_{cid}", width="stretch"):
                    try:
                        service.delete_comment(post_id, cid)
                        if is_editing:
                            st.session_state.forum_editing_comment_id = None
                        st.rerun()
                    except service.DataServiceError as err:
                        st.error(str(err))

                if is_editing:
                    updated_body = st.text_area(
                        "Edit comment",
                        value=comment["body"],
                        height=100,
                        key=f"edit_comment_body_{cid}",
                    )
                    if st.button("Save Comment", type="primary", key=f"save_comment_btn_{cid}"):
                        try:
                            service.update_comment(post_id, cid, updated_body)
                            st.session_state.forum_editing_comment_id = None
                            st.session_state.pop(f"edit_comment_body_{cid}", None)
                            st.rerun()
                        except ValueError as err:
                            st.warning(str(err))
                        except service.DataServiceError as err:
                            st.error(str(err))
                else:
                    st.markdown(comment["body"])

    # Add Comment Section (only processes on button click; Enter in Display Name does nothing,
    # Enter in Comment textarea inserts a normal newline)
    with st.container(key="forum_add_comment_section"):
        st.markdown("#### Add a Comment")
        c_author_key = f"add_comment_author_{post_id}"
        c_body_key = f"add_comment_body_{post_id}"

        c_author = st.text_input(
            "Display Name *",
            placeholder="Your name or handle",
            key=c_author_key,
        )
        c_body = st.text_area(
            "Comment *",
            height=100,
            placeholder="Share your thoughts on this thread...",
            key=c_body_key,
        )
        if st.button("Post Comment", type="primary", key=f"submit_comment_btn_{post_id}"):
            try:
                service.add_comment(post_id, c_author, c_body)
                st.session_state.pop(c_author_key, None)
                st.session_state.pop(c_body_key, None)
                st.rerun()
            except ValueError as err:
                st.warning(str(err))
            except service.DataServiceError as err:
                st.error(str(err))


def _apply_search():
    st.session_state.forum_applied_search = st.session_state.get("forum_search_input", "")
    st.session_state.forum_page = 1


def _clear_all_filters():
    st.session_state.forum_search_input = ""
    st.session_state.forum_applied_search = ""
    st.session_state.forum_filter_category = ""
    st.session_state.forum_sort = "Newest first"
    st.session_state.forum_page = 1


def _go_to_page(target_page):
    st.session_state.forum_page = int(target_page)


def _page_sequence(current_page, total_pages):
    """Build compact page list with ellipsis when total_pages > 7 (e.g. 1, 2, 3, ..., 10)."""
    if total_pages <= 7:
        return list(range(1, total_pages + 1))
    pages = {1, total_pages, current_page, current_page - 1, current_page + 1}
    valid = sorted(p for p in pages if 1 <= p <= total_pages)
    seq = []
    prev = None
    for p in valid:
        if prev is not None and p - prev > 1:
            seq.append("…")
        seq.append(p)
        prev = p
    return seq


def _render_feed():
    head, create_col = st.columns([3.5, 1.2], vertical_alignment="center")
    head.write("Tactical breakdowns, scouting briefs, and open VCT community discussions.")
    head.caption("Hybrid polyglot CRUD: post metadata in PostgreSQL; tags & comments in MongoDB.")

    show_create = st.session_state.get("forum_show_create", False)
    with create_col:
        with st.container(key="forum_close_editor" if show_create else "forum_new_post"):
            if st.button(
                "Close Editor" if show_create else "New Post",
                type="primary",
                width="stretch",
                key="forum_toggle_create",
            ):
                st.session_state.forum_show_create = not show_create
                st.rerun()

    if st.session_state.get("forum_show_create"):
        with st.container(border=True):
            st.markdown("### Create a New Forum Post")
            _render_post_form(mode="create")
        st.divider()

    # Search (Enter or Search button) + Category & Sort filters
    s_col, s_btn_col, cat_col, sort_col = st.columns([2.2, 0.7, 1.2, 1.1], gap="small", vertical_alignment="bottom")
    with s_col:
        with st.container(key="forum_search_box"):
            st.text_input(
                "Search",
                placeholder="Search title, body, author, or tag...",
                key="forum_search_input",
                on_change=_apply_search,
            )
    with s_btn_col:
        if st.button("Search", type="primary", width="stretch", key="forum_search_btn"):
            _apply_search()
    with cat_col:
        cat_options = [""] + list(service.CATEGORIES)
        category = st.selectbox(
            "Category",
            cat_options,
            format_func=lambda c: c or "All categories",
            key="forum_filter_category",
        )
    with sort_col:
        sort_by = st.selectbox("Sort by", ["Newest first", "Most commented"], key="forum_sort")

    applied_search = st.session_state.get("forum_applied_search", "")

    try:
        data = service.list_posts(
            search=applied_search,
            category=category,
            sort_by=sort_by,
        )
    except service.DataServiceError as err:
        st.error(f"{err} Ensure `007_forum_posts.sql` has been executed on Neon PostgreSQL and `MONGODB_URI` is valid.")
        if st.button("Retry loading forums", type="primary"):
            st.rerun()
        return

    posts = data["posts"]
    total = len(posts)

    # Reset page to 1 whenever category/sort changes
    filter_sig = (applied_search, category, sort_by)
    if st.session_state.get("forum_filter_sig") != filter_sig:
        st.session_state.forum_filter_sig = filter_sig
        st.session_state.forum_page = 1

    count_col, clear_col = st.columns([4, 1.2], vertical_alignment="center")
    count_col.caption(f"{total} {'thread' if total == 1 else 'threads'} found")
    with clear_col:
        with st.container(key="forum_clear_filters_btn"):
            st.button(
                "Clear all filters",
                on_click=_clear_all_filters,
                key="forum_clear_filters_action",
            )

    if not posts:
        st.info("No forum threads match the current filters. Clear all filters or create a new post.")
        return

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(st.session_state.get("forum_page", 1), total_pages))
    st.session_state.forum_page = page
    visible = posts[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    for post in visible:
        with st.container(border=True):
            top_left, top_right = st.columns([4.2, 1], vertical_alignment="center")
            with top_left:
                st.markdown(f"#### {post['title']}")
                st.caption(
                    f"By **{post['author_name']}** · {_format_timestamp(post['created_at'])} · "
                    f"**{post['comment_count']}** {'comment' if post['comment_count'] == 1 else 'comments'}"
                )
            with top_right:
                st.button(
                    "Open thread",
                    key=f"open_forum_post_{post['post_id']}",
                    on_click=_open_post,
                    args=(post["post_id"],),
                    width="stretch",
                )

            _render_entity_badges(post)

            snippet = post["body"].replace("\n", " ").strip()
            if len(snippet) > 220:
                snippet = snippet[:220].rsplit(" ", 1)[0] + "…"
            st.write(snippet)

    # Hyperlink-style Pagination Controls: Showing X–Y of Z | Previous  1  2  3 ... Next
    start_idx = (page - 1) * PAGE_SIZE + 1
    end_idx = min(page * PAGE_SIZE, total)
    seq = _page_sequence(page, total_pages)

    nav_weights = [3.6, 0.85] + [0.38] * len(seq) + [0.65]
    nav_cols = st.columns(nav_weights, vertical_alignment="center")
    nav_cols[0].caption(f"Showing {start_idx}–{end_idx} of {total} / Page {page} of {total_pages}")

    with nav_cols[1]:
        with st.container(key="forum_page_link_prev"):
            st.button(
                "Previous",
                disabled=page == 1,
                on_click=_go_to_page,
                args=(page - 1,),
                key="forum_prev_page",
            )

    for idx, item in enumerate(seq):
        with nav_cols[2 + idx]:
            if item == "…":
                st.markdown("<span style='color:#64748b;'>…</span>", unsafe_allow_html=True)
            else:
                is_current = item == page
                container_key = "forum_page_link_active" if is_current else f"forum_page_link_num_{item}"
                with st.container(key=container_key):
                    st.button(
                        str(item),
                        disabled=is_current,
                        on_click=_go_to_page,
                        args=(item,),
                        key=f"forum_page_num_{item}",
                    )

    with nav_cols[-1]:
        with st.container(key="forum_page_link_next"):
            st.button(
                "Next",
                disabled=page == total_pages,
                on_click=_go_to_page,
                args=(page + 1,),
                key="forum_next_page",
            )


def render():
    _inject_forum_ui_enhancements()
    st.title("Forums")
    selected_post_id = st.session_state.get("forum_selected_post_id")
    if selected_post_id is not None:
        _render_detail(selected_post_id)
    else:
        _render_feed()