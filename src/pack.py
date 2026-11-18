"""Zip the fonts for the site: formal, fancy, or both (TTF for apps, WOFF2 for web, plus the license)."""
import os, zipfile
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(R, "docs", "dl"); os.makedirs(OUT, exist_ok=True)
SETS = {"Ajor": ["Ajor-"], "AjorFancy": ["AjorFancy-"], "Ajor-All": ["Ajor-", "AjorFancy-"]}
for name, prefixes in SETS.items():
    with zipfile.ZipFile(os.path.join(OUT, name + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(os.path.join(R, "fonts"))):
            if any(f.startswith(p) for p in prefixes):
                z.write(os.path.join(R, "fonts", f), ("ttf/" if f.endswith(".ttf") else "web/") + f)
        z.write(os.path.join(R, "OFL.txt"), "OFL.txt")
    print(name, os.path.getsize(os.path.join(OUT, name + ".zip")) // 1024, "KB")
