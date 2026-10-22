"""Convert Blogger post HTML into clean Quarto Markdown."""

import re
import shutil
import subprocess
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

JUNK_TAGS = ["style", "script", "xml", "meta", "link", "title"]
INLINE_WRAPPERS = ["span", "font", "u", "small", "abbr", "big", "center"]
KEEP_ATTRS = {
    "a": {"href"},
    "img": {"src", "alt"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
BLOCK_TAGS = {
    "p", "ul", "ol", "dl", "blockquote", "table", "pre", "hr", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6",
}
IMAGE_HOSTS = ("googleusercontent.com", "blogspot.com", "blogger.com")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
PANDOC_FORMAT = "markdown" + "".join(
    f"-{ext}"
    for ext in [
        "raw_html", "native_divs", "native_spans", "fenced_divs",
        "bracketed_spans", "link_attributes", "header_attributes",
        "implicit_figures", "smart",
    ]
)
VIDEO_MARKER = "QUARTOVIDEOMARKER"


def html_to_markdown(html, image_handler=None):
    """Convert Blogger HTML to Markdown, optionally rewriting image sources."""
    soup = BeautifulSoup(html, "html.parser")
    videos = clean(soup, image_handler)
    markdown = run_pandoc(str(soup))
    return insert_videos(markdown, videos)


def clean(soup, image_handler):
    remove_junk(soup)
    upgrade_linked_images(soup)
    convert_caption_tables(soup)
    if image_handler:
        rewrite_images(soup, image_handler)
    videos = replace_iframes(soup)
    for tag in soup.find_all(INLINE_WRAPPERS):
        tag.unwrap()
    strip_attributes(soup)
    blocks_to_breaks(soup)
    paragraphize(soup)
    for quote in soup.find_all("blockquote"):
        paragraphize(quote)
    for cell in soup.find_all(["li", "td", "th", "dd", "dt"]):
        strip_edge_breaks(cell)
    return videos


def remove_junk(soup):
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in soup.find_all(JUNK_TAGS):
        tag.decompose()
    for tag in soup.find_all(lambda t: ":" in t.name):
        tag.unwrap()
    for text in soup.find_all(string=lambda s: "\xa0" in s):
        text.replace_with(text.replace("\xa0", " "))


def is_image_url(url):
    parsed = urlparse(url or "")
    return parsed.netloc.endswith(IMAGE_HOSTS) or parsed.path.lower().endswith(
        IMAGE_EXTENSIONS
    )


def only_child_image(anchor):
    children = [c for c in anchor.contents if not is_blank(c)]
    if len(children) == 1 and isinstance(children[0], Tag) and children[0].name == "img":
        return children[0]
    return None


def upgrade_linked_images(soup):
    """Replace <a href=full><img src=thumb></a> with a full-size <img>."""
    for anchor in soup.find_all("a"):
        img = only_child_image(anchor)
        if img and is_image_url(anchor.get("href")):
            img["src"] = anchor["href"]
            anchor.replace_with(img)


def convert_caption_tables(soup):
    """Turn Blogger's image+caption tables into captioned images."""
    for table in soup.find_all("table", class_="tr-caption-container"):
        caption = table.find(class_="tr-caption")
        alt = " ".join(caption.get_text(" ").split()) if caption else ""
        images = table.find_all("img")
        for img in images:
            img["alt"] = alt
        paragraphs = [wrap(soup, img.extract(), "p") for img in images]
        if paragraphs:
            table.replace_with(*paragraphs)
        else:
            table.decompose()


def wrap(soup, node, name):
    tag = soup.new_tag(name)
    tag.append(node)
    return tag


def rewrite_images(soup, image_handler):
    for img in soup.find_all("img"):
        new_src = image_handler(img.get("src", ""))
        if new_src:
            img["src"] = new_src
        else:
            drop_image(img)


def drop_image(img):
    parent = img.parent
    img.decompose()
    if parent.name == "a" and not parent.get_text(strip=True):
        parent.decompose()


def replace_iframes(soup):
    videos = []
    for iframe in soup.find_all("iframe"):
        videos.append(iframe.get("src", "").split("?")[0])
        marker = soup.new_tag("p")
        marker.string = f"{VIDEO_MARKER}{len(videos) - 1}"
        iframe.replace_with(marker)
    return videos


def insert_videos(markdown, videos):
    for index, url in enumerate(videos):
        markdown = markdown.replace(f"{VIDEO_MARKER}{index}", f"{{{{< video {url} >}}}}")
    return markdown


def strip_attributes(soup):
    for tag in soup.find_all(True):
        keep = KEEP_ATTRS.get(tag.name, set())
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep}


def ends_with_break(tag):
    children = [c for c in tag.contents if not is_blank(c)]
    return bool(children) and isinstance(children[-1], Tag) and children[-1].name == "br"


def blocks_to_breaks(soup):
    """Unwrap <div> (one line) and <p> (paragraph) into <br> separators."""
    for tag in reversed(soup.find_all(["div", "p"])):
        breaks = 2 if tag.name == "p" else 0 if ends_with_break(tag) else 1
        for _ in range(breaks):
            tag.append(soup.new_tag("br"))
        tag.unwrap()


def is_blank(node):
    return isinstance(node, NavigableString) and not node.strip()


def is_break(node):
    return isinstance(node, Tag) and node.name == "br"


def is_block(node):
    return isinstance(node, Tag) and node.name in BLOCK_TAGS


def paragraphize(container):
    """Group inline content into <p> elements, splitting on double <br>."""
    soup = BeautifulSoup("", "html.parser")
    items, current, breaks = [], [], 0
    for node in [child.extract() for child in list(container.contents)]:
        if is_break(node):
            breaks += 1
        elif is_blank(node):
            if current and not breaks:
                current.append(node)
        elif is_block(node):
            items, current, breaks = flush(soup, items, current) + [node], [], 0
        else:
            if breaks >= 2:
                items, current = flush(soup, items, current), []
            elif breaks == 1 and current:
                current.append(soup.new_tag("br"))
            current.append(node)
            breaks = 0
    for item in flush(soup, items, current):
        container.append(item)


def flush(soup, items, current):
    while current and is_blank(current[-1]):
        current.pop()
    if not current:
        return items
    paragraph = soup.new_tag("p")
    for node in current:
        paragraph.append(node)
    return items + [paragraph]


def strip_edge_breaks(tag):
    for index in (0, -1):
        while tag.contents and (is_blank(tag.contents[index]) or is_break(tag.contents[index])):
            tag.contents[index].extract()


def pandoc_command():
    if shutil.which("pandoc"):
        return ["pandoc"]
    return ["quarto", "pandoc"]


def run_pandoc(html):
    result = subprocess.run(
        pandoc_command() + ["-f", "html", "-t", PANDOC_FORMAT, "--wrap=none"],
        input=html,
        capture_output=True,
        text=True,
        check=True,
    )
    return re.sub(r"\n{3,}", "\n\n", result.stdout).strip()
