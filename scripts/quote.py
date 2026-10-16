"""Fetch today's quote from ZenQuotes and draw it as quote.svg, in the same style as the rest of the profile.

Run by .github/workflows/profile.yml once a day:  python3 scripts/quote.py dist/quote.svg
Text is turned into shapes with the fonts in assets/fonts, so it looks the same on every device.
"""
import datetime, io, json, os, sys, textwrap, urllib.request
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")
W = 1200

FALLBACK = [
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Simplicity is the soul of efficiency.", "Austin Freeman"),
    ("Programs must be written for people to read, and only incidentally for machines to execute.", "Harold Abelson"),
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
]


def fetch():
    try:
        req = urllib.request.Request("https://zenquotes.io/api/today", headers={"User-Agent": "profile-readme"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        q, a = data[0]["q"].strip(), data[0]["a"].strip()
        if q and "too many requests" not in q.lower():
            return q, a, True
    except Exception as e:
        print("ZenQuotes failed, using fallback:", e)
    q, a = FALLBACK[datetime.date.today().toordinal() % len(FALLBACK)]
    return q, a, False


# ---------- text to shapes (falls back to plain <text> if the libraries are missing) ----------
_cache = {}


def _font(name):
    if name not in _cache:
        from fontTools.ttLib import TTFont
        import uharfbuzz as hb
        f = TTFont(os.path.join(FONTS, name + ".woff2"))
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        data = buf.getvalue()
        tt = TTFont(io.BytesIO(data))
        _cache[name] = (tt, hb.Font(hb.Face(data)), tt["head"].unitsPerEm)
    return _cache[name]


def _shape(txt, name, size, tracking):
    import uharfbuzz as hb
    tt, font, upem = _font(name)
    b = hb.Buffer()
    b.add_str(txt)
    b.guess_segment_properties()
    hb.shape(font, b, {"kern": True, "liga": True})
    order, s, x, out = tt.getGlyphOrder(), size / upem, 0.0, []
    for info, pos in zip(b.glyph_infos, b.glyph_positions):
        out.append((order[info.codepoint], x + pos.x_offset * s))
        x += pos.x_advance * s + tracking
    return out, x - tracking, s


def text(txt, x, y, fill, name, size, anchor="start", tracking=0.0, css=""):
    try:
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        tt, _, _ = _font(name)
        glyphs, w, s = _shape(txt, name, size, tracking)
        x -= w / 2 if anchor == "middle" else w if anchor == "end" else 0
        gs = tt.getGlyphSet()
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        for g, gx in glyphs:
            gs[g].draw(TransformPen(pen, (s, 0, 0, -s, x + gx, y)))
        return f'<path d="{pen.getCommands()}" fill="{fill}"/>'
    except Exception:
        fam = "'JetBrains Mono',Consolas,monospace" if "mono" in name else "Outfit,'Segoe UI',Roboto,Arial,sans-serif"
        weight = name.split("-")[-1]
        ta = {"start": "start", "middle": "middle", "end": "end"}[anchor]
        return (f'<text x="{x}" y="{y}" text-anchor="{ta}" font-family="{fam}" font-weight="{weight}" font-size="{size}" '
                f'letter-spacing="{tracking}" fill="{fill}">{escape(txt)}</text>')


def card(q, a, from_api):
    size = 30 if len(q) < 110 else 26 if len(q) < 200 else 22
    lines = textwrap.wrap(q, width=int(1700 / size))
    if len(lines) > 1:  # balance the lines so there is no lonely last word
        lines = textwrap.wrap(q, width=max(20, -(-len(q) // len(lines)) + 6))
    lines = lines[:5]
    lh, top = size * 1.45, 132
    H = int(top + lh * len(lines) + 96)
    today = datetime.date.today().strftime("%d %B %Y").lstrip("0").upper()

    body = text(f"THOUGHT OF THE DAY  ·  {today}", 600, 62, "#a78bfa", "jetbrains-mono-500", 13, "middle", 2.5)
    body += text("“", 70, 150, "#d946ef", "outfit-600", 150).replace("<path ", '<path fill-opacity="0.25" ', 1)
    body += text("”", 1075, H + 40, "#22d3ee", "outfit-600", 150, "end").replace("<path ", '<path fill-opacity="0.2" ', 1)
    for i, ln in enumerate(lines):
        body += text(ln, 600, top + i * lh, "#eef0ff", "outfit-400", size, "middle")
    body += f'<rect x="560" y="{H - 70}" width="80" height="3" rx="1.5" fill="url(#rule)"/>'
    body += text(a, 600, H - 36, "#fbcfe8", "outfit-600", 18, "middle")
    body += text("via ZenQuotes" if from_api else "from my own list", 1170, H - 16, "#6b7398", "outfit-400", 11, "end")

    label = escape(f"Thought of the day: {q} by {a}", {'"': "&quot;"})
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">
<defs>
  <linearGradient id="cardbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0d1f"/><stop offset="1" stop-color="#130d33"/></linearGradient>
  <radialGradient id="cardglow" cx="0.9" cy="0" r="0.75"><stop offset="0" stop-color="#8b5cf6" stop-opacity="0.2"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient>
  <radialGradient id="cardglow2" cx="0.05" cy="1" r="0.6"><stop offset="0" stop-color="#3b82f6" stop-opacity="0.1"/><stop offset="1" stop-color="#3b82f6" stop-opacity="0"/></radialGradient>
  <linearGradient id="cardedge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee" stop-opacity="0.55"/><stop offset="0.5" stop-color="#8b5cf6" stop-opacity="0.35"/><stop offset="1" stop-color="#d946ef" stop-opacity="0.55"/></linearGradient>
  <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#d946ef"/></linearGradient>
  <clipPath id="cardclip"><rect width="{W}" height="{H}" rx="12"/></clipPath>
</defs>
<g clip-path="url(#cardclip)">
  <rect width="{W}" height="{H}" fill="url(#cardbg)"/><rect width="{W}" height="{H}" fill="url(#cardglow)"/><rect width="{W}" height="{H}" fill="url(#cardglow2)"/>
  {body}
</g>
<rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="12" fill="none" stroke="url(#cardedge)" stroke-width="1.5"/>
</svg>'''


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "quote.svg"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    q, a, ok = fetch()
    with open(out, "w", encoding="utf-8") as f:
        f.write(card(q, a, ok))
    print("wrote", out, "|", a, "|", q)
