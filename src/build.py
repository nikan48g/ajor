"""Build Ajor (اجر) fonts from Dastkhat (OFL, itself derived from Vazirmatn).

Ajor        <- DastkhatDiamond : formal, rounded corners, diamond dots
Ajor Fancy  <- DastkhatBarDots : round dots, round sarkesh, joined dots, cat hamza
Usage: python build.py   (needs fonttools, shapely, brotli)
"""
import os
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely.geometry import Polygon, box, Point, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, nearest_points
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "_ref", "fonts", "Main")
OUT = os.path.join(HERE, "..", "fonts")

# family, base dir, corner radius as a fraction of stem width, cat hamza?, dot scale
STYLES = [
    ("Ajor", "DastkhatDiamond", 0.14, False, 1.3),
    ("Ajor Fancy", "DastkhatBarDots", 0.26, True, 1.35),
]
WEIGHTS = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Regular": 400, "Medium": 500,
           "SemiBold": 600, "Bold": 700, "ExtraBold": 800, "Black": 900}


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


def split_dots(g):
    parts = list(g.geoms) if hasattr(g, "geoms") else [g]
    def dot(p):
        x0, y0, x1, y1 = p.bounds
        return len(parts) > 1 and p.area < 120000 and x1 - x0 < 600 and y1 - y0 < 600 and not p.interiors
    return [p for p in parts if not dot(p)], [p for p in parts if dot(p)]


def keep_joins(body, orig, adv, w):
    """Rounding must not notch the strokes that connect to the neighbouring letter: restore the original edge band there."""
    add = []
    for x in (0, adv):
        hit = orig.intersection(box(x - 3, -3000, x + 3, 4000))
        for h in getattr(hit, "geoms", [hit]):
            if h.is_empty:
                continue
            y0, y1 = h.bounds[1], h.bounds[3]
            add.append(orig.intersection(box(x - w, y0 - 1, x + w, y1 + 1)))
            # overlap the neighbour by a few units: abutting outlines show a hairline seam in Word/GDI
            add.append(affinity.translate(orig.intersection(box(x - 6, y0 - 1, x + 6, y1 + 1)), -8 if x == 0 else 8, 0))
    return unary_union([body] + add) if add else body


def process(gs, n, adv, r, dotk, spread, stem):
    g = region(gs, n)
    rest, dots = split_dots(g)
    if not dots or not rest:  # no letter body (e.g. colon): just round it
        return keep_joins(round_geom(g, r), g, adv, 2.2 * r)
    orig_rest = unary_union(rest)
    body = keep_joins(unary_union([round_geom(p, r) for p in rest]), orig_rest, adv, 2.2 * r)
    cen = unary_union(dots).centroid
    out = []
    for p in dots:
        d0 = p.distance(orig_rest)
        q = affinity.scale(p, dotk, dotk, origin="centroid")
        if spread and len(dots) > 1:  # keep diamonds apart; joined-dot style lets them fuse
            c = p.centroid
            q = affinity.translate(q, (c.x - cen.x) * (dotk - 1), (c.y - cen.y) * (dotk - 1))
        q = round_geom(q, r)
        target = max(d0, 0.2 * stem)  # dots must never touch the letter body
        for _ in range(80):
            if q.distance(body) >= target:
                break
            pb, pd = nearest_points(body, q)
            vx, vy = pd.x - pb.x, pd.y - pb.y
            if vx == 0 and vy == 0:
                vx, vy = q.centroid.x - body.centroid.x, q.centroid.y - body.centroid.y
            L = (vx * vx + vy * vy) ** 0.5 or 1
            q = affinity.translate(q, 6 * vx / L, 6 * vy / L)
        out.append(q)
    if spread:  # formal style: diamonds must not fuse; fancy style joins dots on purpose
        gap = 0.22 * stem
        for _ in range(120):
            moved = False
            for i in range(len(out)):
                for j in range(i + 1, len(out)):
                    if out[i].distance(out[j]) < gap:
                        a, b = out[i].centroid, out[j].centroid
                        vx, vy = b.x - a.x, b.y - a.y
                        L = (vx * vx + vy * vy) ** 0.5 or 1
                        out[i] = affinity.translate(out[i], -2 * vx / L, -2 * vy / L)
                        out[j] = affinity.translate(out[j], 2 * vx / L, 2 * vy / L)
                        moved = True
            if not moved:
                break
    return unary_union([body] + out)


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
    """Recognisable cat head: wide head, two tall pointed ears, eye holes, nose, mouth, whiskers."""
    head = affinity.scale(Point(0, 230).buffer(1, quad_segs=16), 330, 250)
    ear_l = Polygon([(-330, 300), (-300, 720), (-40, 470)])
    ear_r = affinity.scale(ear_l, -1, 1, origin=(0, 0))
    cat = unary_union([head, ear_l, ear_r]).buffer(12).buffer(-12)
    whisk = []
    for sx in (-1, 1):
        for (y0, y1) in ((215, 300), (150, 150), (85, 0)):
            whisk.append(LineString([(sx * 280, y0), (sx * 530, y1)]).buffer(15, cap_style="round"))
    cat = unary_union([cat] + whisk)
    eyes = [affinity.scale(Point(x, 290).buffer(1, quad_segs=8), 46, 66) for x in (-135, 135)]
    nose = Polygon([(-45, 190), (45, 190), (0, 135)])
    mouth = [LineString([(0, 135), (0, 100), (-70, 70), (-120, 95)]).buffer(11, cap_style="round"),
             LineString([(0, 100), (70, 70), (120, 95)]).buffer(11, cap_style="round")]
    return cat.difference(unary_union(eyes + [nose] + mouth))


def paw():
    """Cat paw print: four oval toes arcing over one big pad."""
    pad = unary_union([affinity.scale(Point(0, 0).buffer(1, quad_segs=12), 230, 170),
                       Point(-120, 50).buffer(120, quad_segs=10), Point(120, 50).buffer(120, quad_segs=10)])
    toes = []
    for x, y, ang in ((-270, 330, 28), (-100, 450, 8), (100, 450, -8), (270, 330, -28)):
        t = affinity.scale(Point(0, 0).buffer(1, quad_segs=10), 72, 108)
        toes.append(affinity.translate(affinity.rotate(t, ang, origin=(0, 0)), x, y))
    return unary_union([pad] + toes)


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


def add_hamza_cat_ligature(font):
    from fontTools.ttLib.tables import otTables as ot
    ham = font.getBestCmap()[0x0621]
    lig = ot.Ligature(); lig.Component = [ham]; lig.LigGlyph = "ajor.cat"
    st = ot.LigatureSubst(); st.Format = 1; st.ligatures = {ham: [lig]}
    lk = ot.Lookup(); lk.LookupType = 4; lk.LookupFlag = 0; lk.SubTable = [st]; lk.SubTableCount = 1
    g = font["GSUB"].table
    g.LookupList.Lookup.append(lk); g.LookupList.LookupCount = len(g.LookupList.Lookup)
    new = g.LookupList.LookupCount - 1
    for fr in g.FeatureList.FeatureRecord:  # shapers read only the first feature of a tag, so join the existing liga
        if fr.FeatureTag == "liga":
            fr.Feature.LookupListIndex.append(new); fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)


def set_names(font, family, style):
    n = font["name"]
    ps = (family + "-" + style).replace(" ", "")
    n.names = [x for x in n.names if x.nameID not in {1, 2, 3, 4, 6, 16, 17, 21, 22, 25}]
    ribbi = style in ("Regular", "Bold")
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        n.setName(family if ribbi else f"{family} {style}", 1, pid, eid, lid)
        n.setName(style if ribbi else "Regular", 2, pid, eid, lid)
        n.setName(f"{family} {style}; Ajor 0.2", 3, pid, eid, lid)
        n.setName(f"{family} {style}", 4, pid, eid, lid)
        n.setName(ps, 6, pid, eid, lid)
        n.setName(family, 16, pid, eid, lid)  # typographic family keeps Ajor and Ajor Fancy apart
        n.setName(style, 17, pid, eid, lid)
        n.setName("Ajor derives from Dastkhat and Vazirmatn (OFL 1.1).", 10, pid, eid, lid)


def build(family, src, rfrac, cat, dotk):
    for style, wclass in WEIGHTS.items():
        f = TTFont(os.path.join(REF, src, "TTF", f"{src}-{style}.ttf"))
        gs = f.getGlyphSet()
        glyf = f["glyf"]
        stem = region(gs, "uni0627").bounds
        r = max(3, rfrac * (stem[2] - stem[0]))
        todo = [n for n in f.getGlyphOrder() if not glyf[n].isComposite() and glyf[n].numberOfContours > 0]
        new = {n: to_glyph(process(gs, n, f['hmtx'][n][0], r, dotk, not cat, stem[2] - stem[0])) for n in todo}
        for n, g in new.items():
            glyf[n] = g

        add_glyph(f, "ajor.cat", 0xE000, affinity.scale(cat_face(), 1.15, 1.15, origin=(0, 0)))
        add_glyph(f, "ajor.paw", 0xE001, affinity.scale(paw(), 1.1, 1.1, origin=(0, 0)))
        add_hamza_cat_ligature(f)  # two hamzas in a row become the cat; a single hamza stays a hamza
        empty = [n for n in todo if glyf[n].numberOfContours == 0]
        assert not empty, empty[:10]
        set_names(f, family, style)
        f["OS/2"].usWeightClass = wclass
        f["OS/2"].fsSelection = (f["OS/2"].fsSelection & ~0x61) | (0x20 if style == "Bold" else 0x40 if style == "Regular" else 0)
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
