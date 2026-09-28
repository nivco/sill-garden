# Growth agent lessons

Durable rules for `daily_growth_agent`, `content_agent`, `traffic_optimizer`, and YouTube automation.

- Playbook: `products/analytics/working-playbook.json`
- Session retros (questions → decisions → shipped): `products/growth/session-retros/`
- Action impact log: `products/growth/action-impact-log.json`

## How the agent must learn

1. **Read session retros** every run — what we asked, how we decided, what shipped.
2. **Record every auto action** with baseline GA4/GSC/YT metrics.
3. **Re-score after 3 days (and again at 7)** — promote WORKING / demote IGNORE in the playbook.
4. **Repeat what lifted sessions / clicks / affiliate / YT→site**; do not blindly repeat flat or negative patches.

## Decision framework (from 2026-09-28 kit-first cycle)

1. Diagnose bottleneck with live metrics before shipping more content.
2. When `sessions_7d ≈ 0`: enrichment + distribution > new thin guides.
3. Monetize with **physical kit stacks only** — never AI-spittable digital products.
4. Automate what APIs allow; leave human-only steps as paste packs (GSC Request indexing, Studio pin, Reddit).
5. After money URLs ship: index/nudge → distribute → **measure impact** → update playbook.

## What worked this cycle

1. Physical kit stacks (`/kits/*`, refills) + tools (kit-picker, year-one-cost).
2. GSC Request indexing is manual; automate sitemap + IndexNow + inspection.
3. YouTube: kit links first in descriptions + channel comments on top Shorts.
4. Soft-skip YouTube API quota (no false failure emails).

## Agent must do similarly

| Signal | Do this |
|---|---|
| `sessions_7d = 0` | Kit-first Reddit/Pinterest/YT; pause thin guides |
| Affiliate clicks = 0 | Kit/refill CTAs + year-one-cost |
| YT views > 0, YT→site = 0 | Refresh descriptions + kit comments |
| New money page shipped | PRIORITY nudge + GSC P0 list + distribution |
| Prior action measured positive | Repeat pattern; keep in WORKING playbook |
| Prior action measured negative | Do not spam the same patch; try kit-first acquisition instead |
