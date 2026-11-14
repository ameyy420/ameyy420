#!/usr/bin/env python3
"""Generate a neofetch-style GitHub profile card (dark_mode.svg + light_mode.svg).

Usage:
    pip install pillow
    python generate.py              # uses config.json (+ photo.jpg if present)
"""
import json
import os
import urllib.request
from html import escape

CFG = json.load(open("config.json", encoding="utf-8"))

# ---------- ASCII art from a photo ----------
RAMP = "@%#*+=-:. "  # dark -> light (for dark background we invert below)
CHAR_W = 8.5  # approx width of one monospace char at font-size 14


def photo_to_ascii(path, cols=48, invert=False):
    from PIL import Image, ImageOps

    ramp = RAMP[::-1] if invert else RAMP
    img = Image.open(path).convert("L")
    img = ImageOps.equalize(ImageOps.autocontrast(img, cutoff=1))
    w, h = img.size
    rows = int(cols * (h / w) * 0.5)  # characters are ~2x taller than wide
    img = img.resize((cols, rows))
    px = img.load()
    lines = []
    for y in range(rows):
        line = ""
        for x in range(cols):
            v = px[x, y] / 255
            line += ramp[int(v * (len(ramp) - 1))]
        lines.append(line.rstrip())
    return lines


def get_ascii(invert=False):
    # 1) a photo next to the script: convert it and cache the result in ascii.txt
    if os.path.exists("photo.jpg") or os.path.exists("photo.png"):
        p = "photo.jpg" if os.path.exists("photo.jpg") else "photo.png"
        try:
            cols = CFG.get("ascii_cols", 48)
            with open("ascii.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(photo_to_ascii(p, cols, False)))
            return photo_to_ascii(p, cols, invert)
        except Exception as e:  # pillow missing, bad file, ...
            print("ASCII conversion failed:", e)
    # 2) no photo (e.g. in the GitHub Action): reuse the saved ascii.txt
    if os.path.exists("ascii.txt"):
        lines = open("ascii.txt", encoding="utf-8").read().split("\n")
        if invert:
            table = str.maketrans(RAMP, RAMP[::-1])
            lines = [l.translate(table) for l in lines]
        return lines
    return [
        "      .-''''-.      ",
        "     /  o  o  \\     ",
        "    |    __    |    ",
        "     \\  \\__/  /     ",
        "      '-.__.-'      ",
        "   put photo.jpg    ",
        "   next to this     ",
        "   script & rerun   ",
    ]


# ---------- optional live GitHub stats (public API, no token) ----------
def github_stats(user):
    out = {}
    token = os.environ.get("GITHUB_TOKEN")  # set automatically inside GitHub Actions
    try:
        headers = {"User-Agent": "profile-card"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        def get(url):
            req = urllib.request.Request(url, headers=headers)
            return json.load(urllib.request.urlopen(req, timeout=15))

        u = get(f"https://api.github.com/users/{user}")
        out["Repos"] = u["public_repos"]
        out["Followers"] = u["followers"]
        repos = get(f"https://api.github.com/users/{user}/repos?per_page=100")
        out["Stars"] = sum(r["stargazers_count"] for r in repos)

        if token:  # contributions over the last year (needs GraphQL + token)
            q = {"query": "query($l:String!){user(login:$l){contributionsCollection"
                          "{contributionCalendar{totalContributions}}}}",
                 "variables": {"l": user}}
            req = urllib.request.Request("https://api.github.com/graphql",
                                         data=json.dumps(q).encode(), headers=headers)
            d = json.load(urllib.request.urlopen(req, timeout=15))
            out["Contributions"] = d["data"]["user"]["contributionsCollection"][
                "contributionCalendar"]["totalContributions"]
    except Exception as e:
        print("Could not fetch live stats (using config values):", e)
    return out


# ---------- SVG ----------
THEMES = {
    "dark_mode.svg": dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", val="#a5d6ff",
                          dim="#8b949e", accent="#7ee787", ascii="#8b949e"),
    "light_mode.svg": dict(bg="#f6f8fa", fg="#24292f", key="#953800", val="#0a3069",
                           dim="#57606a", accent="#116329", ascii="#57606a"),
}


def build(theme, ascii_lines, info_rows):
    LINE = 20
    left_x, top = 15, 30
    afs = CFG.get("ascii_font", 14)  # font size of the portrait only
    a_line = afs * 1.2
    right_x = left_x + int(CFG.get("ascii_cols", 48) * afs * 0.6) + 30
    longest = 0
    for r in info_rows:
        if r[0] == "kv":
            longest = max(longest, 24 + len(str(r[2])))
        elif r[0] in ("title", "section"):
            longest = max(longest, 56)
    W = max(700, int(right_x + longest * CHAR_W + 25))
    height = int(max(len(ascii_lines) * a_line, len(info_rows) * LINE) + top + 20)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
         f'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="14">',
         f'<rect width="100%" height="100%" rx="12" fill="{theme["bg"]}"/>']

    # ascii portrait
    for i, line in enumerate(ascii_lines):
        s.append(f'<text x="{left_x}" y="{top + i * a_line:.1f}" font-size="{afs}" '
                 f'fill="{theme["ascii"]}" xml:space="preserve">{escape(line)}</text>')

    # info block
    for i, row in enumerate(info_rows):
        y = top + i * LINE
        kind = row[0]
        if kind == "title":
            s.append(f'<text x="{right_x}" y="{y}" fill="{theme["accent"]}" font-weight="bold">'
                     f'{escape(row[1])}</text>')
        elif kind == "section":
            dashes = "—" * max(2, 52 - len(row[1]))
            s.append(f'<text x="{right_x}" y="{y}" fill="{theme["fg"]}">- {escape(row[1])} '
                     f'<tspan fill="{theme["dim"]}">{dashes}</tspan>-</text>')
        elif kind == "kv":
            k, v = row[1], row[2]
            dots = "." * max(2, 22 - len(k))
            s.append(f'<text x="{right_x}" y="{y}" xml:space="preserve">'
                     f'<tspan fill="{theme["key"]}">{escape(k)}</tspan>'
                     f'<tspan fill="{theme["dim"]}">:{dots} </tspan>'
                     f'<tspan fill="{theme["val"]}">{escape(str(v))}</tspan></text>')
        # blank rows just advance y
    s.append("</svg>")
    return "\n".join(s)


def main():
    stats = github_stats(CFG["username"]) if CFG.get("fetch_live_stats", True) else {}
    rows = [("title", f'{CFG["username"]}@github')]
    for section, items in CFG["sections"].items():
        rows.append(("blank",))
        rows.append(("section", section))
        for k, v in items.items():
            rows.append(("kv", k, v))
    rows.append(("blank",))
    rows.append(("section", "GitHub Stats"))
    merged = {**CFG.get("stats", {}), **stats}
    for k, v in merged.items():
        rows.append(("kv", k, v))

    for name, theme in THEMES.items():
        # on a dark background, light pixels should be the dense characters
        art = get_ascii(invert=name.startswith("dark"))
        with open(name, "w", encoding="utf-8") as f:
            f.write(build(theme, art, rows))
        print("wrote", name)


if __name__ == "__main__":
    main()
