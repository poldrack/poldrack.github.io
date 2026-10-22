"""Fetch and parse posts and comments from a Blogger JSON feed."""

import json
import posixpath
import urllib.request
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (blog archiver)"


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_entries(feed_url, page_size=150, get_json=get_json):
    """Return all entries of a Blogger feed, following start-index pages."""
    entries, start = [], 1
    while True:
        url = f"{feed_url}?alt=json&start-index={start}&max-results={page_size}"
        page = get_json(url)["feed"].get("entry", [])
        entries.extend(page)
        if len(page) < page_size:
            return entries
        start += len(page)


def slug_from_url(url):
    return posixpath.basename(urlparse(url).path).removesuffix(".html")


def _date(entry):
    return entry["published"]["$t"][:10]


def _alternate_link(entry):
    return next(link["href"] for link in entry["link"] if link["rel"] == "alternate")


def parse_post(entry):
    url = _alternate_link(entry)
    return {
        "id": entry["id"]["$t"],
        "title": entry["title"]["$t"],
        "date": _date(entry),
        "url": url,
        "slug": slug_from_url(url),
        "html": entry["content"]["$t"],
        "categories": [c["term"] for c in entry.get("category", [])],
        "comments": [],
    }


def parse_comment(entry):
    return {
        "post_id": entry["thr$in-reply-to"]["ref"],
        "author": entry["author"][0]["name"]["$t"],
        "date": _date(entry),
        "html": entry["content"]["$t"],
    }


def attach_comments(posts, comments):
    """Add each comment to its parent post, in date order."""
    by_id = {post["id"]: post for post in posts}
    for comment in sorted(comments, key=lambda c: c["date"]):
        if comment["post_id"] in by_id:
            by_id[comment["post_id"]]["comments"].append(comment)
