import re

import pytest

from poldrack_github_io.blogger_html import html_to_markdown

BLOGGER_IMG = "https://blogger.googleusercontent.com/img/b/XYZ"


def test_div_paragraphs_separated_by_empty_divs():
    html = '<div class="MsoNormal">First para.</div><div class="MsoNormal"><br />\n</div><div class="MsoNormal">Second para.</div>'
    assert html_to_markdown(html) == "First para.\n\nSecond para."


def test_consecutive_divs_are_separate_lines():
    md = html_to_markdown("<div>Line one</div><div>Line two</div>")
    assert md == "Line one\\\nLine two"


def test_double_br_starts_new_paragraph():
    assert html_to_markdown("A sentence.<br />\n<br />\nAnother one.") == "A sentence.\n\nAnother one."


def test_single_br_is_line_break():
    assert html_to_markdown("Roses<br />Violets") == "Roses\\\nViolets"


def test_p_elements_are_paragraphs():
    assert html_to_markdown("<p>One</p><p>Two</p>") == "One\n\nTwo"


def test_word_markup_is_removed():
    html = (
        "<!--StartFragment--><style>p.MsoNormal {margin: 0}</style>"
        "<xml><w:WordDocument></w:WordDocument></xml>"
        '<div class="MsoNormal">Hi<span style="mso-spacerun: yes;">&nbsp; </span>there<o:p></o:p></div>'
    )
    assert html_to_markdown(html) == "Hi there"


def test_inline_formatting_and_links():
    html = '<div><b>Platform</b>: see <i>my</i> <a href="http://x.com">site</a></div>'
    assert html_to_markdown(html) == "**Platform**: see *my* [site](http://x.com)"


def test_lists_preserved():
    md = html_to_markdown("Intro<ul><li>one</li><li>two<br /></li></ul>After")
    assert re.search(r"^-\s+one$", md, re.M)
    assert re.search(r"^-\s+two$", md, re.M)
    assert md.startswith("Intro\n\n") and md.endswith("\n\nAfter")


def test_headings_preserved():
    assert html_to_markdown("<h3>Section</h3>Text") == "### Section\n\nText"


def test_blockquote_paragraphs():
    md = html_to_markdown("<blockquote>Quote one<br /><br />Quote two</blockquote>")
    assert md == "> Quote one\n>\n> Quote two"


def test_no_html_attributes_leak():
    html = '<div style="text-align: left;" class="MsoNormal"><span style="color: red">Red</span></div>'
    assert html_to_markdown(html) == "Red"


def test_linked_image_uses_full_size_target():
    html = f'<div class="separator"><a href="{BLOGGER_IMG}/s1600/a.jpg" style="margin: 1em"><img border="0" height="240" src="{BLOGGER_IMG}/s320/a.jpg" width="320" /></a></div>'
    assert html_to_markdown(html) == f"![]({BLOGGER_IMG}/s1600/a.jpg)"


def test_image_linking_elsewhere_keeps_link():
    html = '<a href="http://example.com/page"><img src="http://example.com/a.png" /></a>'
    assert html_to_markdown(html) == "[![](http://example.com/a.png)](http://example.com/page)"


def test_caption_table_becomes_captioned_image():
    html = (
        '<table class="tr-caption-container" style="float: left;"><tbody>'
        f'<tr><td><a href="{BLOGGER_IMG}/s1600/pie.jpg"><img src="{BLOGGER_IMG}/s320/pie.jpg" /></a></td></tr>'
        '<tr><td class="tr-caption">The <b>finished</b> product</td></tr>'
        "</tbody></table>Text after"
    )
    md = html_to_markdown(html)
    assert md == f"![The finished product]({BLOGGER_IMG}/s1600/pie.jpg)\n\nText after"


def test_data_tables_preserved():
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    md = html_to_markdown(html)
    assert "<table" not in md
    assert re.search(r"A\s+B", md) and re.search(r"1\s+2", md)


def test_youtube_iframe_becomes_video_shortcode():
    html = "<div><iframe width='320' src='https://www.youtube.com/embed/X4TK5AJq56w?feature=player_embedded'></iframe></div>"
    assert html_to_markdown(html) == "{{< video https://www.youtube.com/embed/X4TK5AJq56w >}}"


def test_image_handler_rewrites_sources():
    html = '<img src="http://a.com/x.png" /><br /><br /><img src="http://a.com/y.png" />'
    md = html_to_markdown(html, image_handler=lambda src: src.replace("http://a.com/", ""))
    assert md == "![](x.png)\n\n![](y.png)"


def test_image_handler_returning_none_drops_image():
    html = 'Before<a href="https://www.facebook.com/x"><img src="http://dead.com/x.png" /></a>'
    assert html_to_markdown(html, image_handler=lambda src: None) == "Before"


@pytest.mark.parametrize("raw", ["", "<div><br /></div>", "<!--StartFragment-->  <br />"])
def test_empty_content(raw):
    assert html_to_markdown(raw) == ""


MONO = '<span style="font-family: Courier New, Courier, monospace;">{}</span>'


def test_monospace_lines_become_fenced_code_block():
    html = (
        "<div>Example:</div><div><br /></div>"
        + "".join(
            f"<div>{MONO.format(line)}</div>"
            for line in ["&gt; library(NHANES)\n", "&gt; head(NHANES)\n", "&nbsp;&nbsp;&nbsp;ID &lt;NA&gt; [1]"]
        )
        + "<div><br /></div><div>After</div>"
    )
    assert html_to_markdown(html) == (
        "Example:\n\n```\n> library(NHANES)\n> head(NHANES)\n   ID <NA> [1]\n```\n\nAfter"
    )


def test_inline_monospace_becomes_code():
    html = "<div>Run " + MONO.format("ls -l") + " now</div>"
    assert html_to_markdown(html) == "Run `ls -l` now"


def test_nested_monospace_spans():
    html = "<div>" + MONO.format("a " + MONO.format("b")) + "</div>"
    assert html_to_markdown(html) == "```\na b\n```"
