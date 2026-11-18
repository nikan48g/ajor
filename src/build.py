"""Build Ajor (اجر) fonts from Dastkhat (OFL, itself derived from Vazirmatn).

Ajor        <- DastkhatDiamond : formal, rounded corners, diamond dots
Ajor Fancy  <- DastkhatBarDots : round dots, round sarkesh, joined dots, cat hamza
Usage: python build.py   (needs fonttools, shapely, brotli)
"""
import os
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely.geometry import Polygon, box, Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "_ref", "fonts", "Main")
OUT = os.path.join(HERE, "..", "fonts")

# family, base dir, file prefix, rounding radius (font units) per weight, cat hamza?
STYLES = [
    # style -> (Dastkhat weight to start from, corner radius); heavier than Dastkhat on purpose
    ("Ajor", "DastkhatDiamond", {"Regular": ("Medium", 38), "Bold": ("ExtraBold", 50)}, False, 1.45),
    ("Ajor Fancy", "DastkhatBarDots", {"Regular": ("SemiBold", 56), "Bold": ("Black", 70)}, True, 1.45),
]


class Flatten(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.contours, self.cur = [], None

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, a, b, c):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8; u = 1 - t
            self.cur.append((u**3*p0[0] + 3*u*u*t*a[0] + 3*u*t*t*b[0] + t**3*c[0],
                             u**3*p0[1] + 3*u*u*t*a[1] + 3*u*t*t*b[1] + t**3*c[1]))

    def _qCurveToOne(self, a, b):
        p0 = self.cur[-1]
        for i in range(1, 7):
            t = i / 6; u = 1 - t
            self.cur.append((u*u*p0[0] + 2*u*t*a[0] + t*t*b[0], u*u*p0[1] + 2*u*t*a[1] + t*t*b[1]))

    def _closePath(self):
        if self.cur and len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = None

    _endPath = _closePath


def region(gs, name):
    pen = Flatten(gs)
    gs[name].draw(pen)
    polys = []
    for c in pen.contours:
        p = Polygon(c)
        if not p.is_valid:
            p = p.buffer(0)
        if p.area:
            polys.append((Polygon(c).exterior.is_ccw, p))
    polys.sort(key=lambda x: -x[1].area)
    res = Polygon()
    ref = polys[0][0] if polys else False  # largest contour is an outer: same direction = fill, opposite = hole
    for ccw, p in polys:
        res = res.union(p) if ccw == ref else res.difference(p)
    return res


def grow_dots(g, k, spread):
    """Enlarge dot-sized islands about their centre; spread=True also pushes touching dots apart
    (so diamonds do not fuse), spread=False lets them fuse (joined dots)."""
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    if len(parts) < 2:
        return g
    def dot(p):
        x0, y0, x1, y1 = p.bounds
        return p.area < 120000 and x1 - x0 < 600 and y1 - y0 < 600 and not p.interiors
    dots = [p for p in parts if dot(p)]
    rest = [p for p in parts if not dot(p)]
    if not dots:
        return g
    cen = unary_union(dots).centroid
    out = []
    for p in dots:
        q = affinity.scale(p, k, k, origin="centroid")
        if spread and len(dots) > 1:
            c = p.centroid
            q = affinity.translate(q, (c.x - cen.x) * (k - 1), (c.y - cen.y) * (k - 1))
        out.append(q)
    return unary_union(rest + out)


def to_glyph(geom):
    pen = TTGlyphPen(None)
    geoms = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    for g in geoms:
        if g.is_empty or g.geom_type != "Polygon":
            continue
        g = orient(g, sign=-1.0)
        for ring in [g.exterior, *g.interiors]:
            pts = [(round(x), round(y)) for x, y in ring.coords[:-1]]
            ded = [p for i, p in enumerate(pts) if p != pts[i - 1]]
            if len(ded) < 3:
                continue
            pen.moveTo(ded[0])
            for p in ded[1:]:
                pen.lineTo(p)
            pen.closePath()
    return pen.glyph()


def round_geom(g, r):
    for rr in (r, r / 2, r / 4, 0):  # thin ornaments would vanish at full radius
        out = _round(g, rr) if rr else g
        if not out.is_empty:
            return out


def _round(g, r):
    g = g.buffer(r, quad_segs=4).buffer(-r, quad_segs=4)       # soften concave corners
    g = g.buffer(-r, quad_segs=4).buffer(r, quad_segs=4)       # soften convex corners
    return g.simplify(0.7)


def cat_face():
    """Little cat head, ~620 wide, bottom at y=0. Diamond nose nods to the Diamond dots."""
    head = box(-250, 0, 250, 400).buffer(60, quad_segs=6)
    ear = Polygon([(-300, 330), (-310, 600), (-90, 440)])
    cat = unary_union([head, ear, affinity.scale(ear, -1, 1, origin=(0, 0))]).buffer(14).buffer(-14)
    eyes = [Point(x, 250).buffer(36) for x in (-125, 125)]
    nose = Polygon([(0, 170), (36, 130), (0, 90), (-36, 130)])
    mouth = [box(-90, 40, -10, 62), box(10, 40, 90, 62)]
    return cat.difference(unary_union(eyes + [nose] + mouth))


def paw():
    pad = affinity.scale(Point(0, 0).buffer(150, quad_segs=6), 1.2, 0.9)
    toes = [Point(x, y).buffer(70, quad_segs=6) for x, y in ((-210, 230), (-75, 320), (75, 320), (210, 230))]
    return unary_union([affinity.translate(pad, 0, 0)] + toes)


def add_glyph(font, name, cp, geom, extra=70):
    minx, miny, maxx, maxy = geom.bounds
    geom = affinity.translate(geom, extra - minx, 0)
    adv = round(maxx - minx + 2 * extra)
    font["glyf"][name] = to_glyph(geom)
    order = font.getGlyphOrder()
    if name not in order:
        order.append(name); font.setGlyphOrder(order)
    font["hmtx"][name] = (adv, extra)
    if cp:
        for t in font["cmap"].tables:
            if t.isUnicode():
                t.cmap[cp] = name
    return geom, adv


def set_names(font, family, style):
    n = font["name"]
    ps = (family + "-" + style).replace(" ", "")
    drop = {1, 2, 3, 4, 6, 16, 17, 21, 22, 25}
    n.names = [x for x in n.names if x.nameID not in drop]
    typo_ok = style in ("Regular", "Bold")
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        n.setName(family, 1, pid, eid, lid)
        n.setName(style if typo_ok else "Regular", 2, pid, eid, lid)
        n.setName(f"{family} {style}; Ajor 0.1", 3, pid, eid, lid)
        n.setName(f"{family} {style}", 4, pid, eid, lid)
        n.setName(ps, 6, pid, eid, lid)
        n.setName("Ajor derives from Dastkhat and Vazirmatn (OFL 1.1).", 10, pid, eid, lid)


def build(family, src, radii, cat, dotk):
    for style, (srcw, r) in radii.items():
        path = os.path.join(REF, src, "TTF", f"{src}-{srcw}.ttf")
        f = TTFont(path)
        gs = f.getGlyphSet()
        glyf = f["glyf"]
        todo = [n for n in f.getGlyphOrder() if not glyf[n].isComposite() and glyf[n].numberOfContours > 0]
        new = {}
        for n in todo:
            new[n] = to_glyph(round_geom(grow_dots(region(gs, n), dotk, not cat), r))
        for n, g in new.items():
            glyf[n] = g

        cp_cat, cp_paw = 0xE000, 0xE001
        cg, _ = add_glyph(f, "ajor.cat", cp_cat, affinity.scale(cat_face(), 1.5, 1.5, origin=(0, 0)))
        add_glyph(f, "ajor.paw", cp_paw, affinity.scale(paw(), 1.3, 1.3, origin=(0, 0)))
        if cat:  # fancy: hamza itself becomes a little cat
            cmap = f.getBestCmap()
            hn = cmap[0x0621]
            g = affinity.scale(cat_face(), 1.5, 1.5, origin=(0, 0))
            old = glyf[hn]
            ymin = getattr(old, "yMin", 0)
            g, adv = add_glyph(f, hn, None, affinity.translate(g, 0, ymin))
        empty = [n for n in todo if glyf[n].numberOfContours == 0]
        assert not empty, empty[:10]
        set_names(f, family, style)
        f["OS/2"].usWeightClass = 700 if style == "Bold" else 400
        f["OS/2"].fsSelection = (f["OS/2"].fsSelection & ~0x61) | (0x20 if style == "Bold" else 0x40)
        f["head"].macStyle = 1 if style == "Bold" else 0
        os.makedirs(OUT, exist_ok=True)
        base = os.path.join(OUT, f"{family.replace(' ', '')}-{style}")
        f.save(base + ".ttf")
        f.flavor = "woff2"
        f.save(base + ".woff2")
        print("built", base, len(f.getGlyphOrder()), "glyphs")


if __name__ == "__main__":
    for s in STYLES:
        build(*s)
