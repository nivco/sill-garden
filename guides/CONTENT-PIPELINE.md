# Content pipeline — Sill Garden

Goal: grow traffic beyond brand comparisons with howto, troubleshooting, DIY, and cost pages that still monetize Amazon + Click & Grow.

**Automation:** `python scripts/content_agent.py --refresh` + workflow `content-agent.yml` (daily 16:00 UTC).

## Shipped (2026-08)

### Systems / comparisons
- [x] `aerogarden-vs-click-and-grow`
- [x] `compare-aerogarden-models`
- [x] `click-and-grow-vs-idoo-auk`
- [x] `best-countertop-garden-apartments`
- [x] `countertop-garden-system-guide`
- [x] `cheapest-indoor-herb-garden-apartment`
- [x] `quiet-countertop-gardens-studios`
- [x] `countertop-garden-pod-refill-cost`

### Setup / howto / troubleshoot
- [x] `countertop-garden-running-cost`
- [x] `grow-light-schedules-herbs`
- [x] `landlord-safe-indoor-garden-setup`
- [x] `kratky-jar-herbs-apartment`
- [x] `yellow-leaves-leggy-seedlings-indoor-herbs`

### Herbs
- [x] `basil-countertop-first-harvest`
- [x] `mint-windowsill-first-harvest`
- [x] `best-low-light-herbs-apartment`
- [x] `windowsill-herbs-without-kit`

## Image rule

Each guide gets a **unique hero**. Inline photos must not repeat the same file across guides (see `scripts/reassign_guide_images.py`). Prefer Openverse / Wikimedia CC images cataloged in `src/lib/photos.ts`.

## Next backlog (write when GSC shows demand)

1. `chives-windowsill-first-harvest` — herb depth + pots/seeds affiliate  
2. `winter-indoor-herbs-weak-daylight` — seasonal + clip LED  
3. `clean-mold-algae-countertop-garden` — troubleshoot + trays  
4. `grocery-herbs-vs-countertop-garden-breakeven` — cost companion  
5. `auk-vs-click-and-grow-deep-dive` if Auk impressions climb  

## Monetization notes

- Always include 1–2 Amazon `search` or `asin` products plus Click & Grow where silence/convenience fits.
- Pod-cost and troubleshooting pages convert accessories (LED, timer, tray) better than another kit comparison.
- Gardener’s Supply partner is wired in code — add when affiliate URL is live.
