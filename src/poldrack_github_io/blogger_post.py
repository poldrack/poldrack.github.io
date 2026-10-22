"""Write Blogger posts (with comments and images) as Quarto post folders."""

import shutil
import sys
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import yaml

from poldrack_github_io import blogger_feed
from poldrack_github_io.blogger_html import html_to_markdown

AUTHOR = "Russ Poldrack"
BLOG_FEEDS = "https://russpoldrack.blogspot.com/feeds"
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
REMOVED_COMMENT = "This comment has been removed"


def fetch_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": blogger_feed.USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get_content_type()


def frontmatter(post):
    header = {"title": post["title"], "author": AUTHOR, "date": post["date"]}
    if post["categories"]:
        header["categories"] = post["categories"]
    return "---\n" + yaml.safe_dump(header, sort_keys=False, allow_unicode=True) + "---\n"


def quote(markdown):
    return "\n".join(f"> {line}".rstrip() for line in markdown.splitlines())


def render_comment(comment):
    body = quote(html_to_markdown(comment["html"]))
    return f"**{comment['author']}** · {comment['date']}\n\n{body}"


def render_comments(comments, url):
    kept = [c for c in comments if not c["html"].strip().startswith(REMOVED_COMMENT)]
    if not kept:
        return ""
    noun = "comment" if len(kept) == 1 else "comments"
    heading = f"## {len(kept)} {noun} captured from the [original post]({url})"
    return "\n\n".join([heading] + [render_comment(c) for c in kept])


def render_post(post, body, comments):
    origin = f"*This was originally posted on Blogger [here]({post['url']}).*"
    sections = [origin, body] + ([f"---\n\n{comments}"] if comments else [])
    return frontmatter(post) + "\n" + "\n\n".join(sections) + "\n"


def image_suffix(url, content_type):
    suffix = PurePosixPath(urlparse(url).path).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return suffix
    return IMAGE_TYPES.get(content_type)


def image_downloader(post_dir, fetch=fetch_bytes):
    """Return a handler that saves each image locally and returns its filename."""
    count = 0

    def handle(url):
        nonlocal count
        try:
            data, content_type = fetch(url)
        except OSError:
            return None
        if not content_type.startswith("image/"):
            return None
        count += 1
        filename = f"image-{count:02d}{image_suffix(url, content_type) or '.img'}"
        (Path(post_dir) / filename).write_bytes(data)
        return filename

    return handle


def write_post(post, posts_dir, fetch=fetch_bytes):
    post_dir = Path(posts_dir) / post["slug"]
    if post_dir.exists():
        shutil.rmtree(post_dir)
    post_dir.mkdir(parents=True)
    body = html_to_markdown(post["html"], image_downloader(post_dir, fetch))
    comments = render_comments(post["comments"], post["url"])
    (post_dir / "index.qmd").write_text(render_post(post, body, comments))


def load_posts():
    posts = [blogger_feed.parse_post(e) for e in blogger_feed.fetch_entries(f"{BLOG_FEEDS}/posts/default")]
    entries = blogger_feed.fetch_entries(f"{BLOG_FEEDS}/comments/default")
    blogger_feed.attach_comments(posts, [blogger_feed.parse_comment(e) for e in entries])
    return posts


def main(posts_dir="blog/posts"):
    posts = load_posts()
    for post in posts:
        print(f"{post['date']} {post['slug']} ({len(post['comments'])} comments)")
        write_post(post, posts_dir)
    print(f"Wrote {len(posts)} posts to {posts_dir}")


if __name__ == "__main__":
    main(*sys.argv[1:])
