#!/usr/bin/env python3
"""Force unique hero + inline images; drop excess body images when the pool runs out."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "src" / "content" / "guides"
IMG = ROOT / "public" / "images"

HEROES: dict[str, tuple[str, str]] = {
    "aerogarden-vs-click-and-grow.md": ("/images/guide-systems.jpg", "Indoor plant in a pot on a table"),
    "compare-aerogarden-models.md": ("/images/guide-countertop.jpg", "Potted plants on a wooden shelf"),
    "countertop-garden-system-guide.md": ("/images/guide-diy-herbs.jpg", "Kitchen herb mint in a pot"),
    "best-countertop-garden-apartments.md": ("/images/guide-kitchen-herbs.jpg", "Culinary herb plant ready for cooking"),
    "cheapest-indoor-herb-garden-apartment.md": ("/images/guide-compare-budget.jpg", "Smart countertop herb garden kit"),
    "quiet-countertop-gardens-studios.md": ("/images/guide-quiet.jpg", "Young green plant in a quiet corner"),
    "countertop-garden-running-cost.md": ("/images/guide-light.jpg", "Herb leaf close-up under light"),
    "grow-light-schedules-herbs.md": ("/images/guide-troubleshooting.jpg", "Basil leaf detail for light checks"),
    "landlord-safe-indoor-garden-setup.md": ("/images/guide-setup.jpg", "Two plants on a windowsill"),
    "basil-countertop-first-harvest.md": ("/images/guide-basil.jpg", "Basil garden plant"),
    "best-low-light-herbs-apartment.md": ("/images/guide-windowsill.jpg", "Rosemary and herbs on an indoor window"),
    "windowsill-herbs-without-kit.md": ("/images/about-sill.jpg", "Rosemary on an indoor sill"),
}

# Prefer topical inlines first; leftovers fill remaining guides.
PREFERRED: dict[str, list[tuple[str, str]]] = {
    "aerogarden-vs-click-and-grow.md": [
        ("inline-greenery.jpg", "Lush indoor basil greenery"),
        ("inline-basil.jpg", "Living basil by a window"),
    ],
    "compare-aerogarden-models.md": [
        ("inline-cilantro.jpg", "Fresh cilantro and coriander leaves"),
        ("inline-indoor-row.jpg", "Capacity shown as a leafy plant row"),
    ],
    "countertop-garden-system-guide.md": [
        ("inline-counter-plant.jpg", "Compact basil pot on a counter"),
        ("inline-seedlings.jpg", "Young starts in a compact system"),
    ],
    "best-countertop-garden-apartments.md": [
        ("inline-kitchen.jpg", "Kitchen counter with living greenery"),
        ("inline-grow-tray.jpg", "Indoor grow tray with young plants"),
    ],
    "cheapest-indoor-herb-garden-apartment.md": [
        ("inline-pots.jpg", "Budget pots ready for seed starting"),
        ("inline-chives.jpg", "Chives for a cheap first harvest"),
    ],
    "quiet-countertop-gardens-studios.md": [
        ("inline-mint2.jpg", "Quiet herb corner for a small kitchen"),
        ("inline-mint.jpg", "Compact mint suited to silent setups"),
    ],
    "countertop-garden-running-cost.md": [
        ("inline-parsley-alt.jpg", "Parsley as a low-cost ongoing crop"),
        ("inline-basil-alt.jpg", "Basil leaves that justify electricity cost"),
    ],
    "grow-light-schedules-herbs.md": [
        ("inline-led-grow.jpg", "Bottom view of an LED grow fixture"),
        ("inline-rosemary-alt.jpg", "Rosemary foliage under long day schedules"),
    ],
    "landlord-safe-indoor-garden-setup.md": [
        ("inline-oregano.jpg", "Moveable pots that do not need drilling"),
        ("inline-parsley.jpg", "Potted herbs with saucers for spill control"),
    ],
    "basil-countertop-first-harvest.md": [
        ("inline-mint-fresh.jpg", "Companion herbs beside basil on a sill"),
        ("inline-herbs-board.jpg", "Cut basil ready for cooking"),
    ],
    "best-low-light-herbs-apartment.md": [
        ("inline-yellow-plant.jpg", "Yellowing parsley when light is too weak"),
        ("inline-thyme.jpg", "Thyme that handles softer apartment light"),
    ],
    "windowsill-herbs-without-kit.md": [
        ("inline-shelf-herbs.jpg", "Shelf herbs near apartment light"),
        ("inline-seedlings-alt.jpg", "Seedlings started without a hydro kit"),
    ],
}


def main() -> None:
    owned: set[str] = set()
    pools: dict[str, list[tuple[str, str]]] = {}
    for guide, pairs in PREFERRED.items():
        clean: list[tuple[str, str]] = []
        for fn, alt in pairs:
            if not (IMG / fn).is_file():
                continue
            if fn in owned:
                continue
            owned.add(fn)
            clean.append((fn, alt))
        pools[guide] = clean

    leftovers = [
        (p.name, "Indoor herbs for apartments")
        for p in sorted(IMG.glob("inline-*.jpg"))
        if p.name not in owned
    ]

    # Top up each guide to max 2 preferred already; extras from leftovers for guides that need more body slots later
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

        pool = list(pools.get(name, []))
        # also allow leftovers for this guide if body has many images
        local = pool + leftovers
        leftovers = []  # consume sequentially across guides? better: only use guide pool + shared leftover stack
        # restore approach: guide pool first, then shared leftovers
        shared = [
            (p.name, "Indoor herbs for apartments")
            for p in sorted(IMG.glob("inline-*.jpg"))
            if p.name not in owned or any(p.name == fn for fn, _ in pool)
        ]
        # simpler second pass below
        path.write_text(text, encoding="utf-8")

    # Second pass: replace/remove body images with globally unique assignment
    used_inline: set[str] = set()
    leftover_stack = [
        p.name for p in sorted(IMG.glob("inline-*.jpg"))
    ]
    # Prefer preferred order: build queue per guide then global leftover
    guide_queues: dict[str, list[str]] = {}
    reserved: set[str] = set()
    for guide, pairs in pools.items():
        q = []
        for fn, _ in pairs:
            if fn not in reserved:
                reserved.add(fn)
                q.append(fn)
        guide_queues[guide] = q
    global_q = [n for n in leftover_stack if n not in reserved]

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
                return ""  # drop excess / conflict
            used_inline.add(fn)
            alt = "Indoor herbs for apartments"
            for g_pairs in pools.values():
                for f2, a2 in g_pairs:
                    if f2 == fn:
                        alt = a2
            return f"![{alt}](/images/{fn})\n\n"

        # Only replace markdown images in body (after frontmatter)
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
        for fn in re.findall(r"\(/images/(inline-[^)]+)\)", t):
            used_i[fn].append(path.name)
    print("hero dups", {k: v for k, v in used_h.items() if len(v) > 1})
    print("inline dups", {k: v for k, v in used_i.items() if len(v) > 1})
    print("guides", len(list(GUIDES.glob('*.md'))), "unique inlines used", len(used_i))


if __name__ == "__main__":
    main()
