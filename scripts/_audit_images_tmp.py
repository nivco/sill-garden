from pathlib import Path
import re
from collections import defaultdict

guides = Path("src/content/guides")
usage = defaultdict(list)
generic = []

for p in sorted(guides.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^image:\s*(.+)$", text, re.M)
    alt = re.search(r"^imageAlt:\s*(.+)$", text, re.M)
    if m:
        img = m.group(1).strip().strip('"')
        usage[img].append(f"{p.name}:hero")
    for im in re.finditer(r"!\[([^\]]*)\]\((/images/[^\)]+)\)", text):
        a, img = im.group(1), im.group(2)
        usage[img].append(f"{p.name}:inline")
        if a.lower().strip() in ("indoor herbs for apartments", "indoor plant", ""):
            generic.append((p.name, img, a))

bad = {
    "/images/guide-yellow-leaves.jpg": "wood micrograph",
    "/images/guide-systems.jpg": "spider plant",
    "/images/guide-countertop.jpg": "ivy/succulents shelf",
    "/images/guide-mint.jpg": "outdoor mint flower spikes",
    "/images/guide-setup.jpg": "weeping figs (retired)",
    "/images/inline-mold-tray.jpg": "ruins sapling",
    "/images/inline-leggy.jpg": "thermometer not leggy",
    "/images/inline-grow-tray.jpg": "begonias not grow tray",
    "/images/inline-seedlings.jpg": "succulent cuttings",
    "/images/inline-hydro-herbs.jpg": "herbs on book not hydro kit",
    "/images/inline-apartment.jpg": "decor shelves not herbs",
    "/images/inline-cilantro-alt.jpg": "spices not cilantro",
    "/images/inline-harvest.jpg": "chive flowers not harvest",
    "/images/inline-rosemary.jpg": "cat not rosemary",
    "/images/inline-mint.jpg": "strawberry in eggshell",
    "/images/inline-mint2.jpg": "night patio pots",
    "/images/inline-mint-fresh.jpg": "outdoor mint flowers",
    "/images/inline-led-grow.jpg": "DIY RGB electronics not grow fixture",
    "/images/inline-indoor-row.jpg": "outdoor weed field",
    "/images/inline-seedlings-alt.jpg": "farm lettuce field",
    "/images/inline-jar-herbs.jpg": "outdoor NFT tomatoes",
    "/images/inline-water-roots.jpg": "lettuce crate not jar roots",
    "/images/inline-grocery-herbs.jpg": "hoverfly / retired grocery mismatch",
    "/images/inline-chives.jpg": "retired mislabeled chives asset",
    "/images/inline-chives-fresh.jpg": "chive blossoms not leaf harvest",
}

print("=== DUPLICATES ===")
dups = {k: v for k, v in usage.items() if len(v) > 1}
for k, v in sorted(dups.items(), key=lambda x: -len(x[1])):
    print(f"{k} ({len(v)}x)")
    for loc in v:
        print(f"  - {loc}")

print("\n=== BAD ASSETS STILL IN USE ===")
any_bad = False
for b, why in bad.items():
    if b in usage:
        any_bad = True
        print(f"{b} ({why}):")
        for loc in usage[b]:
            print(f"  - {loc}")
if not any_bad:
    print("none of the previously flagged mismatches")

print("\n=== GENERIC ALTS ===")
if not generic:
    print("none")
else:
    for row in generic:
        print(row)

print("\n=== HEROES ===")
for p in sorted(guides.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^image:\s*(.+)$", text, re.M)
    a = re.search(r"^imageAlt:\s*(.+)$", text, re.M)
    img = m.group(1).strip() if m else "?"
    alt = a.group(1).strip() if a else "?"
    print(f"{p.stem}: {img} | {alt}")
