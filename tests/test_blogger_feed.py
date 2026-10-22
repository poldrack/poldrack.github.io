import pytest

from poldrack_github_io import blogger_feed

POST_URL = "https://russpoldrack.blogspot.com/2010/11/my-productivity-toolbox.html"
POST_ID = "tag:blogger.com,1999:blog-123.post-456"


@pytest.fixture
def post_entry():
    return {
        "id": {"$t": POST_ID},
        "published": {"$t": "2010-11-10T08:30:00.000-08:00"},
        "title": {"type": "text", "$t": "My Productivity Toolbox: part 1"},
        "content": {"type": "html", "$t": "<p>Hello</p>"},
        "link": [
            {"rel": "replies", "type": "text/html", "href": POST_URL + "#comment-form"},
            {"rel": "alternate", "type": "text/html", "href": POST_URL},
        ],
        "category": [
            {"scheme": "http://www.blogger.com/atom/ns#", "term": "productivity"},
            {"scheme": "http://www.blogger.com/atom/ns#", "term": "tools"},
        ],
    }


@pytest.fixture
def comment_entry():
    return {
        "id": {"$t": "tag:blogger.com,1999:blog-123.post-999"},
        "published": {"$t": "2010-11-11T09:00:00.000-08:00"},
        "content": {"type": "html", "$t": "Great post!<br />Thanks"},
        "author": [{"name": {"$t": "Jane Doe"}}],
        "thr$in-reply-to": {"href": POST_URL, "ref": POST_ID},
    }


def test_slug_from_url_matches_existing_folder_names():
    assert blogger_feed.slug_from_url(POST_URL) == "my-productivity-toolbox"


def test_parse_post(post_entry):
    post = blogger_feed.parse_post(post_entry)
    assert post["id"] == POST_ID
    assert post["title"] == "My Productivity Toolbox: part 1"
    assert post["date"] == "2010-11-10"
    assert post["url"] == POST_URL
    assert post["slug"] == "my-productivity-toolbox"
    assert post["html"] == "<p>Hello</p>"
    assert post["categories"] == ["productivity", "tools"]
    assert post["comments"] == []


def test_parse_post_without_categories(post_entry):
    del post_entry["category"]
    assert blogger_feed.parse_post(post_entry)["categories"] == []


def test_parse_comment(comment_entry):
    comment = blogger_feed.parse_comment(comment_entry)
    assert comment == {
        "post_id": POST_ID,
        "author": "Jane Doe",
        "date": "2010-11-11",
        "html": "Great post!<br />Thanks",
    }


def test_attach_comments_sorted_by_date(post_entry, comment_entry):
    later = dict(comment_entry, published={"$t": "2011-01-01T00:00:00.000Z"})
    posts = [blogger_feed.parse_post(post_entry)]
    comments = [blogger_feed.parse_comment(c) for c in (later, comment_entry)]
    blogger_feed.attach_comments(posts, comments)
    assert [c["date"] for c in posts[0]["comments"]] == ["2010-11-11", "2011-01-01"]


def test_attach_comments_ignores_orphans(post_entry, comment_entry):
    orphan = dict(comment_entry, **{"thr$in-reply-to": {"ref": "other"}})
    posts = [blogger_feed.parse_post(post_entry)]
    blogger_feed.attach_comments(posts, [blogger_feed.parse_comment(orphan)])
    assert posts[0]["comments"] == []


def test_fetch_entries_paginates_until_empty():
    pages = {
        1: {"feed": {"entry": [{"n": 1}, {"n": 2}]}},
        3: {"feed": {"entry": [{"n": 3}]}},
        4: {"feed": {}},
    }
    requested = []

    def fake_get_json(url):
        start = int(url.split("start-index=")[1].split("&")[0])
        requested.append(url)
        return pages[start]

    entries = blogger_feed.fetch_entries(
        "https://example.blogspot.com/feeds/posts/default",
        page_size=2,
        get_json=fake_get_json,
    )
    assert entries == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert all("alt=json" in u and "max-results=2" in u for u in requested)
