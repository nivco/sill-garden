# Long-tail guide outlines (next to write)

Goal: earn first Google impressions on easier queries than “AeroGarden vs Click & Grow.”
Ship these as normal guides under `src/content/guides/` when ready.

**Automation:** `python scripts/content_agent.py --refresh` researches GSC/network, refreshes FAQ/SEO, and ships curated long-tail pages. Workflow: `content-agent.yml` (daily 16:00 UTC).

**Live signal (2026-08-17):** GSC already shows impressions for `aerogarden vs` (pos ~26)
and `click and grow vs aerogarden` (pos ~37). The comparison guide title/FAQ was tightened
for both query orders — still ship long-tail pages below; don’t only chase the head term.

## Shipped

- [x] `best-low-light-herbs-apartment`
- [x] `cheapest-indoor-herb-garden-apartment`
- [x] `countertop-garden-running-cost`

---

## 1. Cheapest indoor herb garden for apartments (under $50)

**Slug:** `cheapest-indoor-herb-garden-apartment`  
**Cluster:** `systems` · **Type:** `guide`  
**Primary queries:** cheapest indoor herb garden apartment · grow herbs indoors under $50 · budget countertop garden rental  
**Why this wins:** budget intent is less contested than brand comparisons; pairs with Amazon search links + Click & Grow later as the “upgrade.”

### Verdict (draft)
Skip pods for month one. A clip-on LED + three jars (or a small Kratky kit) gets you basil and mint for under $50 if you already have a sunny-ish sill — or under $70 with a basic light.

### Outline
1. **What “cheap” actually costs** — gear vs pods vs electricity (one short table).
2. **Lane A: windowsill soil pots** — when light is enough; tray + 3 herbs.
3. **Lane B: mason-jar Kratky** — silent, rental-safe; link landlord-safe guide.
4. **Lane C: used / small 3-pod kit** — when to buy Click & Grow SG3 vs wait.
5. **Don’t cheap out on** — drip tray, surge strip, one decent clip light.
6. **30-day shopping list** — three Amazon search products + optional Click & Grow partner CTA.
7. **Next:** windowsill-without-kit · landlord-safe · best-countertop-apartments.

### Products (frontmatter)
- Clip-on LED grow light (`search`)
- Kratky mason jar setup (`search`)
- Waterproof boot / drip tray (`search`)
- Optional upgrade: Click & Grow Smart Garden 3 (`partner: click-grow`)

---

## 2. How much does a countertop garden cost to run?

**Slug:** `countertop-garden-running-cost`  
**Cluster:** `setup` · **Type:** `howto`  
**Primary queries:** countertop garden electricity cost · AeroGarden electricity usage · Click and Grow pod cost per month  
**Why this wins:** high commercial intent, clear numbers, natural affiliate disclosure; feeds comparison pages.

### Verdict (draft)
Expect roughly **$2–6/month electricity** for a small LED kit in the US, plus **$8–25/month** if you keep buying branded pods. Soil/refill paths cut the pod line item hard.

### Outline
1. **Three cost buckets** — power · consumables (pods/nutrients) · replacements.
2. **Electricity math** — watts × hours × kWh rate (show US example + note to check local rate).
3. **Pod economics** — Click & Grow vs AeroGarden vs DIY soil; cost per harvest, not per pod.
4. **Hidden costs** — failed first crops, extra light for jars, water changes.
5. **Cheapest steady state** — refillable / soil after you know which herbs you eat.
6. **When a kit still wins** — time > money; link AeroGarden vs Click & Grow.
7. **Next:** basil first harvest · grow light schedules · cheapest under $50.

### Products
- AeroGarden Harvest (`asin`)
- Click & Grow Smart Garden 3 (`partner: click-grow`)
- Clip-on LED grow light (`search`) — for DIY cost lane

---

## 3. Best low-light herbs for apartment windowsills

**Slug:** `best-low-light-herbs-apartment`  
**Cluster:** `herbs` · **Type:** `guide`  
**Primary queries:** herbs for low light apartment · herbs for north facing window · indoor herbs without grow light  
**Why this wins:** herb intent is evergreen; sits next to windowsill-without-kit and grow-light-schedules without cannibalizing them.

### Verdict (draft)
Mint, chives, parsley, and oregano forgive weak sills; basil and rosemary usually need a clip light or a kit. Pick herbs by light first, kit second.

### Outline
1. **Quick light test** — hand shadow / phone lux app; “dim sill” definition.
2. **Herbs that cope** — mint, chives, parsley, oregano (care notes, harvest).
3. **Herbs that struggle** — basil, rosemary, thyme (what fails without LEDs).
4. **No-kit setup** — pots, tray, rotation; link windowsill-without-kit.
5. **When to add light** — clip-on schedule; link grow-light-schedules.
6. **When a kit is simpler** — Click & Grow for basil-heavy cooking.
7. **Next:** basil first harvest · quiet studios · landlord-safe.

### Products
- Clip-on LED grow light (`search`)
- Waterproof boot / drip tray (`search`)
- Click & Grow Smart Garden 3 (`partner: click-grow`) — for basil lane

---

## Write order

1. **Low-light herbs** — fastest to ship, easiest impressions.  
2. **Cheapest under $50** — monetizes search + DIY.  
3. **Running cost** — supports both comparison and kits.

## Google request-indexing (manual, once each)

API cannot do this for normal sites. In [Search Console → URL Inspection](https://search.google.com/search-console):

1. `https://sillgarden.com/guides/best-countertop-garden-apartments/`
2. `https://sillgarden.com/credits/` (optional; low SEO value)

Paste URL → **Request indexing** once. Re-check in a few days via the dashboard indexing card.
