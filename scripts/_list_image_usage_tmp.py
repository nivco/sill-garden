from pathlib import Path
import re

rows = []
for p in sorted(Path("src/content/guides").glob("*.md")):
    t = p.read_text(encoding="utf-8")
    m = re.search(r"^image:\s*(.+)$", t, re.M)
    a = re.search(r"^imageAlt:\s*(.+)$", t, re.M)
    if m:
        rows.append((p.name, "hero", m.group(1).strip(), a.group(1).strip() if a else ""))
    for im in re.finditer(r"!\[([^\]]*)\]\((/images/[^\)]+)\)", t):
        rows.append((p.name, "inline", im.group(2), im.group(1)))

out = Path("scripts/_image_usage_tmp.txt")
out.write_text("\n".join("|".join(r) for r in rows), encoding="utf-8")
print(f"wrote {len(rows)} rows to {out}")
# unique paths
paths = sorted({r[2] for r in rows})
print("unique images:", len(paths))
for p in paths:
    print(p)
