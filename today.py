"""Builds dark_mode.svg and light_mode.svg: a neofetch-style card with the avatar in ASCII
on the left and the profile + live GitHub stats on the right.

Run by .github/workflows/build.yml every day. Locally:  GH_TOKEN=... python today.py
"""
import datetime
import html
import json
import os
import urllib.request

USER = "EXOTARA"
BIRTHDAY = datetime.date(2005, 4, 30)
WIDTH = 60  # characters in one line of the info column

PROFILE = [
    ("header", None),
    ("OS", "Windows 10/11, Linux"),
    ("Uptime", "{uptime}"),
    ("Host", "Open Source"),
    ("Kernel", "Student"),
    ("IDE", "VS Code, Bash"),
    ("blank", None),
    ("Languages.Programming", "JavaScript, C"),
    ("Languages.Learning", "Python, TypeScript"),
    ("Languages.Computer", "HTML, CSS, JSON, LaTeX"),
    ("Languages.Real", "Spanish, English"),
    ("blank", None),
    ("Hobbies.Software", "Linux ricing, Open Source, Modding"),
    ("Hobbies.Security", "Cybersecurity"),
    ("Hobbies.Hardware", "Building PCs, Exploring components"),
    ("blank", None),
    ("section", "Contact"),
    ("Email.Personal", "adlerrodriguez42@gmail.com"),
    ("LinkedIn", "adler-rodriguez-soberanis"),
    ("Discord", "exo_is_dead"),
    ("Reddit", "u/Exxoo01"),
    ("blank", None),
    ("section", "GitHub Stats"),
    ("stats", None),
]

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657",
                 value="#a5d6ff", dots="#616e7f", add="#3fb950", sub="#f85149", art_invert=True),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800",
                  value="#0a3069", dots="#c2cfde", add="#1a7f37", sub="#cf222e", art_invert=False),
}


# ---------- GitHub ----------

def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "bearer " + os.environ["GH_TOKEN"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def repos(field, extra=""):
    out, cursor = [], None
    while True:
        d = gql("""query($login: String!, $cursor: String) { user(login: $login) {
            %s(first: 100, after: $cursor %s) { totalCount
              nodes { nameWithOwner stargazerCount isFork }
              pageInfo { endCursor hasNextPage } } } }""" % (field, extra),
                {"login": USER, "cursor": cursor})["user"][field]
        out += d["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        cursor = d["pageInfo"]["endCursor"]


def loc(name_with_owner, author_id):
    owner, name = name_with_owner.split("/")
    add = sub = commits = 0
    cursor = None
    while True:
        d = gql("""query($owner: String!, $name: String!, $cursor: String, $id: ID!) {
            repository(owner: $owner, name: $name) { defaultBranchRef { target { ... on Commit {
              history(first: 100, after: $cursor, author: { id: $id }) { totalCount
                nodes { additions deletions } pageInfo { endCursor hasNextPage } } } } } } }""",
                {"owner": owner, "name": name, "cursor": cursor, "id": author_id})
        ref = d["repository"]["defaultBranchRef"]
        if not ref:
            return 0, 0, 0
        h = ref["target"]["history"]
        commits = h["totalCount"]
        for n in h["nodes"]:
            add += n["additions"]
            sub += n["deletions"]
        if not h["pageInfo"]["hasNextPage"]:
            return add, sub, commits
        cursor = h["pageInfo"]["endCursor"]


def stats():
    u = gql("query($login: String!) { user(login: $login) { id followers { totalCount } } }",
            {"login": USER})["user"]
    own = [r for r in repos("repositories", ", ownerAffiliations: [OWNER]") if not r["isFork"]]
    contributed = repos("repositoriesContributedTo",
                        ", contributionTypes: [COMMIT, PULL_REQUEST], includeUserRepositories: false")
    add = sub = commits = 0
    for r in own + contributed:
        a, s, c = loc(r["nameWithOwner"], u["id"])
        add, sub, commits = add + a, sub + s, commits + c
    return dict(repos=len(own), contributed=len(contributed),
                stars=sum(r["stargazerCount"] for r in own),
                commits=commits, followers=u["followers"]["totalCount"],
                add=add, sub=sub, loc=add - sub)


# ---------- text ----------

def uptime(today):
    y, m, d = today.year - BIRTHDAY.year, today.month - BIRTHDAY.month, today.day - BIRTHDAY.day
    if d < 0:
        m -= 1
        prev = today.replace(day=1) - datetime.timedelta(days=1)
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    plural = lambda n, w: "%d %s%s" % (n, w, "" if n == 1 else "s")
    return "%s, %s, %s" % (plural(y, "year"), plural(m, "month"), plural(d, "day"))


def esc(s):
    return html.escape(s, quote=False)


def kv(key, value, width=WIDTH):
    """'. Key: ...... value' padded with dots to `width` characters."""
    dots = max(1, width - len(key) - len(value) - 5)
    return [("dots", ". "), ("key", key), ("text", ":"), ("dots", " " + "." * dots + " "), ("value", value)]


def info_lines(s, today):
    lines = []
    for key, value in PROFILE:
        if key == "header":
            title = "%s@github " % USER.lower()
            lines.append([("text", title), ("text", "-" * (WIDTH - len(title)))])
        elif key == "blank":
            lines.append([("text", "")])
        elif key == "section":
            title = "- %s " % value
            lines.append([("text", title), ("text", "-" * (WIDTH - len(title)))])
        elif key == "stats":
            lines += stat_lines(s)
        else:
            lines.append(kv(key, value.format(uptime=uptime(today))))
    return lines


def stat_lines(s):
    def pair(k1, v1, k2, v2):
        left = kv(k1, v1, 33)
        right = kv(k2, v2, 25)
        return left + [("text", " | ")] + right[1:]
    loc_text = "{:,}".format(s["loc"])
    tail = " ( {:,}++, {:,}-- )".format(s["add"], s["sub"])
    first = kv("Repos", "%d {Contributed: %d}" % (s["repos"], s["contributed"]), 33)
    rest = kv("Stars", str(s["stars"]), 25)
    line3 = kv("Lines of Code on GitHub", loc_text, WIDTH - len(tail))
    return [
        first + [("text", " | ")] + rest[1:],
        pair("Commits", "{:,}".format(s["commits"]), "Followers", str(s["followers"])),
        line3 + [("text", " ( "), ("add", "{:,}++".format(s["add"])), ("text", ", "),
                 ("sub", "{:,}--".format(s["sub"])), ("text", " )")],
    ]


# ---------- svg ----------

def svg(theme, art, lines):
    t = THEMES[theme]
    art_lines = art[theme]
    rows = max(len(art_lines), len(lines))
    height = 40 + rows * 20
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" font-family="ConsolasFallback,Consolas,monospace" '
           'width="985px" height="%dpx" font-size="16px">' % height,
           '<style>.key{fill:%s}.value{fill:%s}.dots{fill:%s}.add{fill:%s}.sub{fill:%s}text,tspan{white-space:pre}</style>'
           % (t["key"], t["value"], t["dots"], t["add"], t["sub"]),
           '<rect width="985px" height="%dpx" fill="%s" rx="15" stroke="%s"/>' % (height, t["bg"], t["border"]),
           '<text x="15" y="30" fill="%s" class="ascii">' % t["text"]]
    for i, a in enumerate(art_lines):
        out.append('<tspan x="15" y="%d">%s</tspan>' % (30 + i * 20, esc(a)))
    out.append('</text>')
    out.append('<text x="400" y="30" fill="%s">' % t["text"])
    for i, parts in enumerate(lines):
        spans = "".join(
            esc(txt) if cls == "text" else '<tspan class="%s">%s</tspan>' % (cls, esc(txt))
            for cls, txt in parts)
        out.append('<tspan x="400" y="%d">%s</tspan>' % (30 + i * 20, spans))
    out.append('</text></svg>')
    return "\n".join(out) + "\n"


def main():
    today = datetime.date.today()
    with open("ascii.txt") as f:
        light = f.read().rstrip("\n").split("\n")
    with open("ascii_dark.txt") as f:
        dark = f.read().rstrip("\n").split("\n")
    lines = info_lines(stats(), today)
    for theme in THEMES:
        with open("%s_mode.svg" % theme, "w") as f:
            f.write(svg(theme, {"dark": dark, "light": light}, lines))


if __name__ == "__main__":
    main()
