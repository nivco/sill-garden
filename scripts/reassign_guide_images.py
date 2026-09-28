#!/usr/bin/env python3
"""Force unique hero + inline images; drop excess body images when the pool runs out."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "src" / "content" / "guides"
IMG = ROOT / "public" / "images"

# Intentionally unused (mismatched subjects from prior audits).
BLOCKED = {
    "guide-countertop.jpg",
    "guide-systems.jpg",
    "guide-yellow-leaves.jpg",
    "inline-cilantro-alt.jpg",
    "inline-grow-tray.jpg",
    "inline-harvest.jpg",
    "inline-hydro-herbs.jpg",
    "inline-leggy.jpg",
    "inline-mold-tray.jpg",
    "inline-rosemary.jpg",
    "inline-seedlings.jpg",
    "guide-mint.jpg",
    "inline-mint.jpg",
    "inline-mint2.jpg",
    "inline-mint-fresh.jpg",
    "inline-apartment.jpg",
}

HEROES: dict[str, tuple[str, str]] = {
    "aerogarden-vs-click-and-grow.md": (
        "/images/guide-compare-budget.jpg",
        "Click & Grow Smart Garden with herbs under a built-in LED",
    ),
    "compare-aerogarden-models.md": (
        "/images/kit-aerogarden-harvest.jpg",
        "AeroGarden countertop hydroponic kit growing vegetables under LED light",
    ),
    "countertop-garden-system-guide.md": (
        "/images/kit-click-grow-smart-garden.jpg",
        "Compact countertop garden kit for apartment systems",
    ),
    "best-countertop-garden-apartments.md": (
        "/images/guide-kitchen-herbs.jpg",
        "Culinary herb plant ready for cooking",
    ),
    "cheapest-indoor-herb-garden-apartment.md": (
        "/images/guide-herbs.jpg",
        "Basil and rosemary in pots — a low-cost apartment herb start",
    ),
    "quiet-countertop-gardens-studios.md": ("/images/guide-quiet.jpg", "Young green plant in a quiet corner"),
    "countertop-garden-running-cost.md": ("/images/guide-light.jpg", "Herb leaf close-up under light"),
    "grow-light-schedules-herbs.md": (
        "/images/guide-troubleshooting.jpg",
        "Leafy herb close-up for checking light stress",
    ),
    "landlord-safe-indoor-garden-setup.md": ("/images/guide-setup.jpg", "Two plants on a windowsill"),
    "basil-countertop-first-harvest.md": (
        "/images/guide-basil.jpg",
        "Outdoor basil plant — still useful foliage, pinch blooms early",
    ),
    "best-low-light-herbs-apartment.md": (
        "/images/guide-windowsill.jpg",
        "Rosemary and herbs on an indoor window",
    ),
    "windowsill-herbs-without-kit.md": ("/images/about-sill.jpg", "Rosemary on an indoor sill"),
    "yellow-leaves-leggy-seedlings-indoor-herbs.md": (
        "/images/inline-yellow-plant.jpg",
        "Curly parsley with yellowing leaves that need a light or water check",
    ),
    "mint-windowsill-first-harvest.md": (
        "/images/guide-diy-herbs.jpg",
        "Potted mint on a bright windowsill",
    ),
    "kratky-jar-herbs-apartment.md": ("/images/guide-kratky.jpg", "Simple hydroponic herb setup indoors"),
    "countertop-garden-pod-refill-cost.md": (
        "/images/guide-pod-cost.jpg",
        "Basil leaves representing ongoing herb harvest value",
    ),
    "click-and-grow-vs-idoo-auk.md": (
        "/images/guide-idoo-compare.jpg",
        "Compact potted plants suited to apartment counters",
    ),
}

PREFERRED: dict[str, list[tuple[str, str]]] = {
    "aerogarden-vs-click-and-grow.md": [
        ("inline-greenery.jpg", "Lush indoor basil greenery"),
        ("inline-basil-alt.jpg", "Basil leaves — the herb most countertop kits grow first"),
        ("inline-chives-fresh.jpg", "Fresh chives — a common refill herb after the first pod cycle"),
    ],
    "compare-aerogarden-models.md": [
        ("inline-cilantro.jpg", "Fresh cilantro and coriander leaves"),
        ("inline-indoor-row.jpg", "Capacity shown as a leafy plant row"),
    ],
    "countertop-garden-system-guide.md": [
        ("inline-counter-plant.jpg", "Compact basil pot on a counter"),
        ("inline-seedlings-alt.jpg", "Herb seedlings started in paper cups near a window"),
    ],
    "best-countertop-garden-apartments.md": [
        ("inline-kitchen.jpg", "Kitchen counter with living greenery"),
        ("inline-herbs-board.jpg", "Coriander seedlings in labeled cups — a simple first setup"),
    ],
    "cheapest-indoor-herb-garden-apartment.md": [
        ("inline-pots.jpg", "Budget pots ready for seed starting"),
        ("inline-chives.jpg", "Chives for a cheap first harvest"),
    ],
    "quiet-countertop-gardens-studios.md": [
        ("inline-herb-close.jpg", "Leafy herb under bright growing light — cover or schedule lights at night"),
    ],
    "countertop-garden-running-cost.md": [
        ("inline-parsley-alt.jpg", "Parsley as a low-cost ongoing crop"),
    ],
    "grow-light-schedules-herbs.md": [
        ("inline-led-grow.jpg", "Bottom view of an LED grow fixture"),
        ("inline-rosemary-alt.jpg", "Rosemary foliage under long day schedules"),
        ("inline-leaves.jpg", "Potted rosemary under a long daily light schedule"),
    ],
    "landlord-safe-indoor-garden-setup.md": [
        ("inline-oregano.jpg", "Moveable pots that do not need drilling"),
        ("inline-parsley.jpg", "Potted herbs with saucers for spill control"),
    ],
    "basil-countertop-first-harvest.md": [
        ("inline-basil.jpg", "Basil by a window — pinch flower spikes so leaves stay sweet"),
    ],
    "best-low-light-herbs-apartment.md": [
        ("inline-thyme.jpg", "Thyme that handles softer apartment light"),
    ],
    "windowsill-herbs-without-kit.md": [
        ("inline-shelf-herbs.jpg", "Shelf herbs near apartment light"),
        ("hero-sill.jpg", "Basil and rosemary in pots on a bright sill"),
    ],
    "yellow-leaves-leggy-seedlings-indoor-herbs.md": [],
    "mint-windowsill-first-harvest.md": [
        ("inline-mint-harvest.jpg", "Young mint in a pot — trim leaf pairs, not flower spikes"),
    ],
    "kratky-jar-herbs-apartment.md": [
        ("inline-jar-herbs.jpg", "Jar-friendly hydro herbs on a compact apartment setup"),
        ("inline-water-roots.jpg", "Roots reaching nutrient solution with an air gap"),
    ],
    "countertop-garden-pod-refill-cost.md": [
        ("inline-refill.jpg", "Fresh basil harvest that has to justify refill cost"),
        ("inline-grocery-herbs.jpg", "Grocery clamshell herbs vs growing your own"),
    ],
    "click-and-grow-vs-idoo-auk.md": [],
}


def main() -> None:
    owned: set[str] = set()
    pools: dict[str, list[tuple[str, str]]] = {}
    for guide, pairs in PREFERRED.items():
        clean: list[tuple[str, str]] = []
        for fn, alt in pairs:
            if fn in BLOCKED:
                continue
            if not (IMG / fn).is_file():
                continue
            if fn in owned:
                continue
            owned.add(fn)
            clean.append((fn, alt))
        pools[guide] = clean

    leftovers = [
        (p.name, p.stem.replace("-", " ").title())
        for p in sorted(IMG.glob("*.jpg"))
        if p.name not in owned and p.name not in BLOCKED and not p.name.startswith("og-")
    ]

    for guide in pools:
        while len(pools[guide]) < 2 and leftovers:
            fn, alt = leftovers.pop(0)
            owned.add(fn)
            pools[guide].append((fn, alt))

    img_re = re.compile(r"!\[[^\]]*\]\(/images/[^)]+\)\n?")
    for name, (hero, halt) in HEROES.items():
        path = GUIDES / name
        if not path.is_file():
            print("missing", name)
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^image:\s*.*$", f"image: {hero}", text, count=1, flags=re.M)
        if re.search(r"^imageAlt:", text, flags=re.M):
            text = re.sub(r"^imageAlt:\s*.*$", f"imageAlt: {halt}", text, count=1, flags=re.M)
        else:
            text = re.sub(r"^(image:\s*.*)$", rf"\1\nimageAlt: {halt}", text, count=1, flags=re.M)
        path.write_text(text, encoding="utf-8")

    used_inline: set[str] = set()
    reserved: set[str] = set()
    guide_queues: dict[str, list[str]] = {}
    alt_for: dict[str, str] = {}
    for guide, pairs in pools.items():
        q = []
        for fn, alt in pairs:
            if fn not in reserved:
                reserved.add(fn)
                q.append(fn)
                alt_for[fn] = alt
        guide_queues[guide] = q
    global_q = [
        p.name
        for p in sorted(IMG.glob("*.jpg"))
        if p.name not in reserved and p.name not in BLOCKED and not p.name.startswith("og-")
    ]

    for name in HEROES:
        path = GUIDES / name
        text = path.read_text(encoding="utf-8")
        queue = list(guide_queues.get(name, []))

        def repl(_m: re.Match[str]) -> str:
            nonlocal queue, global_q
            fn = None
            if queue:
                fn = queue.pop(0)
            elif global_q:
                fn = global_q.pop(0)
            if not fn or fn in used_inline:
                return ""
            used_inline.add(fn)
            alt = alt_for.get(fn, fn.replace("-", " ").replace(".jpg", "").title())
            return f"![{alt}](/images/{fn})\n\n"

        parts = text.split("---", 2)
        if len(parts) < 3:
            print("bad fm", name)
            continue
        body = parts[2]
        body2 = img_re.sub(repl, body)
        body2 = re.sub(r"\n{3,}", "\n\n", body2)
        path.write_text("---" + parts[1] + "---" + body2, encoding="utf-8")
        print("rewrote", name)

    used_h: dict[str, list[str]] = defaultdict(list)
    used_i: dict[str, list[str]] = defaultdict(list)
    for path in GUIDES.glob("*.md"):
        t = path.read_text(encoding="utf-8")
        m = re.search(r"^image:\s*(.*)$", t, re.M)
        if m:
            used_h[m.group(1).strip()].append(path.name)
        for fn in re.findall(r"\(/images/([^)]+)\)", t):
            used_i[fn].append(path.name)
    print("hero dups", {k: v for k, v in used_h.items() if len(v) > 1})
    print("inline dups", {k: v for k, v in used_i.items() if len(v) > 1})
    print("guides", len(list(GUIDES.glob("*.md"))), "unique images used", len(used_i))


if __name__ == "__main__":
    main()
