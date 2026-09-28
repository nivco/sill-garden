# Growth agent lessons (2026-09-28 kit-first cycle)

Durable rules for `daily_growth_agent`, `content_agent`, `traffic_optimizer`, and YouTube automation.
Source of truth also mirrored in `products/analytics/working-playbook.json`.

## What worked this cycle

1. **Physical kit stacks** (`/kits/*`, `/kits/refills/`) + tools (`kit-picker`, `year-one-cost`) beat shipping more guides when `sessions_7d ≈ 0`.
2. **Do not sell AI-spittable digital products** — affiliate physical Amazon / Click & Grow stacks only.
3. **GSC “Request indexing”** is manual for normal pages; automate sitemap + IndexNow + URL Inspection (`nudge_google_indexing.py`). Keep a P0 money URL list for humans.
4. **YouTube**: kit links first in descriptions; channel comments on top Shorts; Studio pin when API/quota blocks. Quota resets ~midnight Pacific — retry `youtube-refresh-descriptions` after that.
5. **Distribution packs** must be kit-first (Reddit / Pinterest / YT), not guide-only.

## Agent must do similarly going forward

| Signal | Do this |
|---|---|
| `sessions_7d = 0` | Pause thin new guides; enqueue kit-first Reddit + Pinterest + YT pin; nudge indexing for money URLs |
| Affiliate clicks = 0 | Strengthen kit/refill CTAs and year-one-cost, not more prose |
| YT views > 0 but YT→site = 0 | Refresh descriptions + post kit comments on top Shorts |
| New money page shipped | Add to `nudge_google_indexing.PRIORITY`, GSC P0 list, distribution packs |
| Want “more content” | Prefer tools/kits/data enrichment over new guide volume |

## Files the agent should keep current

- `products/growth/distribution/latest.json` — kit-first pack
- `products/growth/distribution/gsc-request-indexing-urls.md` — P0 money URLs
- `products/analytics/working-playbook.json` — WORKING / IGNORE rules
- `scripts/youtube_common.py` — description kit block
- `scripts/nudge_google_indexing.py` — PRIORITY money URLs
