# add back rel=me link to mastodon profile

with open('docs/index.html') as f:
    html = f.read()

html = html.replace(
    '<a class="nav-link" href="https://mastodon.online/@Russpoldrack">',
    '<a class="nav-link" href="https://mastodon.online/@Russpoldrack" rel="me">'
)

with open('docs/index.html', 'w') as f:
    f.write(html)