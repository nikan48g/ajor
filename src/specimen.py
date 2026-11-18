"""Word specimen with every weight of both families; fonts are embedded (obfuscated) so it works anywhere."""
import os, re, uuid, zipfile, shutil
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement, parse_xml

W = ["Thin", "ExtraLight", "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")
OUT = os.path.join(FONTS, "..", "Ajor-Specimen-v4.docx")
TXT = "آجر به آجر، معبد ساخته می‌شود. ب پ ت ث ج چ ح خ ش گ ژ ء ۰۱۲۳۴۵۶۷۸۹ \ue000 \ue001"


def fam(f, w):  # Regular/Bold live in the base family, other weights are their own families
    return f if w in ("Regular", "Bold") else f"{f} {w}"


d = Document()
for f, title in (("Ajor", "اجر · رسمی"), ("Ajor Fancy", "اجر فانتزی")):
    for text, size, bold in ((f"{title}  ({f})", 20, True),):
        p = d.add_paragraph(); p.add_run(text).font.size = Pt(size)
    for w in W:
        d.add_paragraph().add_run(f"{f} {w}").font.size = Pt(9)
        p = d.add_paragraph()
        pPr = p._p.get_or_add_pPr(); pPr.insert(0, OxmlElement("w:bidi"))  # no jc: start edge = right
        r = p.add_run(TXT); n = fam(f, w)
        rPr = r._r.get_or_add_rPr()
        rf = OxmlElement("w:rFonts")
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"): rf.set(qn(a), n)
        rPr.append(rf)
        if w == "Bold":
            rPr.append(OxmlElement("w:b")); rPr.append(OxmlElement("w:bCs"))
        for tag in ("w:sz", "w:szCs"):
            e = OxmlElement(tag); e.set(qn("w:val"), "44"); rPr.append(e)
        rPr.append(OxmlElement("w:rtl"))
    d.add_page_break()
tmp = OUT + ".tmp"
d.save(tmp)

# ---- embed fonts ----
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
entries, rels, files = [], [], {}
def add(name, slot, ttf, i):
    g = str(uuid.uuid4()).upper()
    key = bytes.fromhex(g.replace("-", ""))[::-1]
    data = bytearray(open(os.path.join(FONTS, ttf), "rb").read())
    for k in range(32): data[k] ^= key[k % 16]
    files[f"word/fonts/font{i}.odttf"] = bytes(data)
    rels.append(f'<Relationship Id="rIdF{i}" Type="{RNS}/font" Target="fonts/font{i}.odttf"/>')
    return f'<w:embed{slot} r:id="rIdF{i}" w:fontKey="{{{g}}}"/>'
i = 0
for f in ("Ajor", "AjorFancy"):
    for w in W:
        fam_name = fam(f.replace("Fancy", " Fancy"), w)
        emb = ""
        if w == "Regular":
            i += 1; emb += add(fam_name, "Regular", f"{f}-Regular.ttf", i)
            i += 1; emb += add(fam_name, "Bold", f"{f}-Bold.ttf", i)
        elif w != "Bold":
            i += 1; emb += add(fam_name, "Regular", f"{f}-{w}.ttf", i)
        else:
            continue
        entries.append(f'<w:font w:name="{fam_name}"><w:charset w:val="B2"/><w:family w:val="auto"/><w:pitch w:val="variable"/>{emb}</w:font>')

with zipfile.ZipFile(tmp) as zi, zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zo:
    for it in zi.infolist():
        b = zi.read(it.filename)
        s = b.decode("utf-8") if it.filename.endswith((".xml", ".rels")) else None
        if it.filename == "word/fontTable.xml":
            s = s.replace("</w:fonts>", "".join(entries) + "</w:fonts>")
            if "xmlns:r=" not in s.split(">", 2)[1]: s = s.replace("<w:fonts ", f'<w:fonts xmlns:r="{RNS}" ', 1)
            b = s.encode("utf-8")
        elif it.filename == "word/settings.xml":
            s = re.sub(r"(<w:settings[^>]*>)", r"\1<w:embedTrueTypeFonts/>", s, count=1); b = s.encode("utf-8")
        elif it.filename == "[Content_Types].xml":
            s = s.replace("<Default ", '<Default Extension="odttf" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/><Default ', 1); b = s.encode("utf-8")
        zo.writestr(it, b)
    zo.writestr("word/_rels/fontTable.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
    for n, b in files.items(): zo.writestr(n, b)
os.remove(tmp)
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
