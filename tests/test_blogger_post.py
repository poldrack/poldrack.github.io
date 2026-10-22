import yaml
import pytest

from poldrack_github_io import blogger_post

URL = "https://russpoldrack.blogspot.com/2010/11/toolbox.html"


@pytest.fixture
def post():
    return {
        "id": "post-1",
        "title": "Tools: a review",
        "date": "2010-11-10",
        "url": URL,
        "slug": "toolbox",
        "html": '<div>Hello</div><div><br /></div><div><img src="http://img.com/a.png" /></div>',
        "categories": ["productivity"],
        "comments": [
            {"post_id": "post-1", "author": "Jane", "date": "2010-11-11", "html": "Nice!<br /><br />Really."},
            {"post_id": "post-1", "author": "Bob", "date": "2010-11-12", "html": "This comment has been removed by the author."},
        ],
    }


def split_frontmatter(text):
    _, header, body = text.split("---\n", 2)
    return yaml.safe_load(header), body


def test_frontmatter_round_trips_titles_with_colons(post):
    header, _ = split_frontmatter(blogger_post.frontmatter(post))
    assert header == {
        "title": "Tools: a review",
        "author": "Russ Poldrack",
        "date": "2010-11-10",
        "categories": ["productivity"],
    }


def test_frontmatter_omits_empty_categories(post):
    post["categories"] = []
    header, _ = split_frontmatter(blogger_post.frontmatter(post))
    assert "categories" not in header


def test_render_comments_skips_removed_and_quotes_bodies(post):
    md = blogger_post.render_comments(post["comments"], URL)
    assert "## 1 comment captured from the [original post](" + URL + ")" in md
    assert "**Jane** · 2010-11-11\n\n> Nice!\n>\n> Really." in md
    assert "Bob" not in md


def test_render_comments_empty_when_none_remain(post):
    assert blogger_post.render_comments(post["comments"][1:], URL) == ""


def test_render_post_layout(post):
    text = blogger_post.render_post(post, "Body text", "## 1 comment")
    header, body = split_frontmatter(text)
    assert header["title"] == "Tools: a review"
    assert body == (
        f"\n*This was originally posted on Blogger [here]({URL}).*\n\n"
        "Body text\n\n---\n\n## 1 comment\n"
    )


def test_render_post_without_comments(post):
    _, body = split_frontmatter(blogger_post.render_post(post, "Body text", ""))
    assert body.endswith("Body text\n")
    assert "---" not in body


def test_image_downloader_saves_numbered_files(tmp_path):
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        return b"data-" + url.encode(), "image/jpeg"

    handler = blogger_post.image_downloader(tmp_path, fetch=fake_fetch)
    assert handler("http://img.com/photo.PNG") == "image-01.png"
    assert handler("https://blogger.googleusercontent.com/img/b/XYZ/") == "image-02.jpg"
    assert (tmp_path / "image-01.png").read_bytes() == b"data-http://img.com/photo.PNG"
    assert fetched == ["http://img.com/photo.PNG", "https://blogger.googleusercontent.com/img/b/XYZ/"]


def test_image_downloader_returns_none_on_failure(tmp_path):
    def failing_fetch(url):
        raise OSError("404")

    handler = blogger_post.image_downloader(tmp_path, fetch=failing_fetch)
    assert handler("http://dead.com/a.png") is None
    assert list(tmp_path.iterdir()) == []


def test_image_downloader_rejects_non_images(tmp_path):
    handler = blogger_post.image_downloader(tmp_path, fetch=lambda url: (b"<html>", "text/html"))
    assert handler("http://dead.com/a.png") is None


def test_write_post_creates_folder_with_images(tmp_path, post):
    blogger_post.write_post(post, tmp_path, fetch=lambda url: (b"png", "image/png"))
    text = (tmp_path / "toolbox" / "index.qmd").read_text()
    _, body = split_frontmatter(text)
    assert "Hello\n\n![](image-01.png)" in body
    assert "**Jane** · 2010-11-11" in body
    assert (tmp_path / "toolbox" / "image-01.png").read_bytes() == b"png"


def test_write_post_replaces_stale_files(tmp_path, post):
    stale = tmp_path / "toolbox" / "old.png"
    stale.parent.mkdir()
    stale.write_bytes(b"old")
    blogger_post.write_post(post, tmp_path, fetch=lambda url: (b"png", "image/png"))
    assert not stale.exists()
