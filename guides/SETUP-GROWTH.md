# Sill Garden growth automations

Sill’s growth stack mirrors Maker Tool Stack capabilities, adapted to Astro markdown guides (not MTS `guides.json` / Etsy tools).

## What runs automatically

| Workflow | Schedule | What it does |
|----------|----------|--------------|
| `traffic-loop.yml` | every 12h | Analytics + IndexNow/action queue |
| `weekly-analytics.yml` | weekly | Scorecard commit |
| `daily-growth-agent.yml` | daily 15:00 UTC | Learn → safe title/meta patches → distribution pack → optional email |
| `content-agent.yml` | daily 16:00 UTC | Research GSC/network → refresh FAQ/SEO + ship curated new guides |
| `ai-growth.yml` | Tue 14:00 UTC | AI citation probe (demo if no API keys) |
| `youtube-auto-publish.yml` | daily 09:00 + 14:00 UTC | Public Short + long-form video |
| `tier2-distribution.yml` | Thu | Dev.to / Hashnode syndication (when keys exist) |
| `tier2b-distribution.yml` | Sun | Mastodon / Telegram / archive (when keys exist) |
| `youtube-refresh-descriptions.yml` | weekly | Refresh uploaded video descriptions |
| `exec-board.yml` | daily 06:00 UTC | CEO/role diagnosis → board report + KPI ledger + queue |

## Local commands

```powershell
cd E:\Projects\sill-garden
python scripts\daily_growth_agent.py --dry-run
python scripts\daily_growth_agent.py --refresh
python scripts\content_agent.py --dry-run
python scripts\content_agent.py --refresh
python scripts\ai_growth_agent.py --demo --enqueue
python scripts\metrics_learning.py
python scripts\exec_board.py --dry-run --cadence weekly
python scripts\exec_board.py --cadence weekly --skip-email
python scripts\syndicate_guides.py --max 1 --dry-run
python scripts\youtube_planner.py --dry-run
```

Set `AUTOMATION_LIVE=1` only when you want scripts to post/publish externally.

## Content shipped with this stack

Long-tail guides (from the impression plan):

1. `/guides/best-low-light-herbs-apartment/`
2. `/guides/cheapest-indoor-herb-garden-apartment/`
3. `/guides/countertop-garden-running-cost/`

RSS: `https://sillgarden.com/feed.xml`

## Secrets to add (optional)

Copy placeholders from `.env.example`. Highest leverage after Google OAuth:

1. `DEVTO_API_KEY` / Hashnode — syndication
2. `GROWTH_*` SMTP — daily email
3. `OPENAI_API_KEY` or `PERPLEXITY_API_KEY` — live AI citation checks
4. Mastodon / Telegram / Bluesky — social distribution

Without those secrets, workflows still run in dry-run / skip mode and write local packs + board tasks.

**Always commit + push after local growth or exec-board runs** so Cloudflare Pages redeploys any guide SEO patches. Scheduled GitHub Actions already commit their outputs to `main`.
