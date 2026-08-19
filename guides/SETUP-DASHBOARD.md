# Sill Garden ops dashboard (local only — private)

Same idea as Maker Tool Stack’s analytics dashboard, with a clearer summary strip for:

- **Sessions / page views** (GA4)
- **Affiliate clicks** (GA4 `affiliate_click` on Amazon / sponsored links)
- **Search** (Google Search Console)
- **YouTube** (channel API + sessions from YouTube)
- **Amazon earnings** (manual paste — no public API)

## Run

```powershell
cd E:\Projects\sill-garden
python scripts\analytics_summary.py
python scripts\dashboard_server.py
```

Open **http://127.0.0.1:8793/dashboard**

Loading the page paints the cached scorecard, then pulls live GA4 + Search Console
automatically (~10s) and re-runs the traffic optimizer. The header line tells you
which one you are looking at (`live`, or `cached · 12m old`). **Refresh** repeats the
live pull. Restart `dashboard_server.py` after editing it — the process does not reload
its own code.

Also appears on the portfolio shell: `E:\Projects\portfolio-dashboard` → http://127.0.0.1:8792/

## Wire data sources (in order)

1. **GA4 property** for sillgarden.com  
   - Create property → copy Measurement ID `G-XXXX`  
   - Set `PUBLIC_GA4_ID=G-XXXX` in `.env` **and** Cloudflare Pages → Environment variables  
   - Copy numeric Property ID into `GA4_PROPERTY_ID=`  
   - Redeploy site so gtag + `affiliate_click` fire on Amazon CTAs

2. **Search Console**  
   - Add `sillgarden.com` (Domain property preferred)  
   - Submit `https://sillgarden.com/sitemap-index.xml`  
   - Set `GSC_SITE_URL=sc-domain:sillgarden.com`  
   - Grant your Google service account / OAuth access (same as MTS if possible)

3. **Cloudflare** (optional edge stats)  
   - `CLOUDFLARE_ZONE_ID` already defaults in `.env.example`  
   - API token needs Zone Analytics Read

4. **YouTube**
   - Channel: `@sillgarden` (`UCc31HDBMhoJtsmZYk0Fo56w`)
   - Public analytics: `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_HANDLE`
   - Upload OAuth is deliberately separate from MTS so the wrong Brand Account cannot receive a video.

5. **Amazon**  
   - Weekly: edit `products/analytics/amazon-manual.json` with clicks / orders / earnings from Associates Central

Copy `.env.example` → `.env` and fill keys. You can point `GOOGLE_*` at the same MTS secret files via relative paths.

## Outputs

- `products/analytics/latest.json` — scorecard
- `products/analytics/history.json` — last ~90 refreshes
- `products/analytics/amazon-manual.json` — pasted Associates numbers
- `products/traffic/action-queue.json` — traffic optimizer priorities

## GitHub automations (MTS-style)

| Workflow | Schedule | What it does |
|---|---|---|
| `deploy.yml` | on push to `main` | Cloudflare Pages deploy → IndexNow (+ Bing if authorized) |
| `weekly-analytics.yml` | Mon 09:00 UTC | Refresh GA4/GSC/CF scorecard → commit `products/analytics/` |
| `traffic-loop.yml` | every 12h | Analytics refresh → action queue → throttled IndexNow |
| `oauth-health-check.yml` | daily 06:30 UTC | Fail if GA4/GSC OAuth is broken |
| `daily-growth-agent.yml` | daily 15:00 UTC | Learn → safe SEO patches → distribution pack → optional email |
| `ai-growth.yml` | Tue 14:00 UTC | AI citation probe (demo if no API keys) |
| `youtube-auto-publish.yml` | daily 09:00 + 14:00 UTC | Build/upload 1 Short + 1 long-form video (**public**) |
| `youtube-refresh-descriptions.yml` | Mon 13:20 UTC | Refresh uploaded video descriptions/tags |
| `tier2-distribution.yml` | Thu 17:00 UTC | Bing/IndexNow submission → up to 2 Dev.to + Hashnode guide posts |
| `tier2b-distribution.yml` | Sun 18:00 UTC | Wayback capture → newest RSS item to Mastodon + Telegram |
| `exec-board.yml` | daily 06:00 UTC | Per-role diagnosis (SEO/CMO/CRO/…) → board report + KPI ledger + optional email |
| `youtube-publish-one.yml` | manual dispatch | Build + upload a single video by directory name |

### Secrets to set on `nivco/sill-garden`

Already needed for deploy: `CLOUDFLARE_*`, `PUBLIC_GA4_ID`

Also set (reuse MTS values where possible):

- `GOOGLE_USER_TOKEN_JSON` + `GOOGLE_OAUTH_CLIENT_JSON` (OAuth desktop token with Analytics + Search Console)
- `INDEXNOW_KEY` (same as local `.env` / `public/<key>.txt`)
- optional: `BING_WEBMASTER_API_KEY`, `CLOUDFLARE_API_TOKEN`, `YOUTUBE_*`
- distribution: `DEVTO_API_KEY`, `HASHNODE_PAT` and either `HASHNODE_PUBLICATION_ID` or `HASHNODE_PUBLICATION_HOST`
- social: `MASTODON_INSTANCE`, `MASTODON_ACCESS_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
- optional archive: `IA_ACCESS_KEY`, `IA_SECRET_KEY`

All posting scripts are dry-run unless `AUTOMATION_LIVE=1`; missing credentials cause
the relevant platform to be skipped. Bluesky support is implemented as a feed-based
manual script but is intentionally not in the Sunday workflow. Set
`BLUESKY_IDENTIFIER` and an app password in `BLUESKY_APP_PASSWORD` before enabling it.

Distribution previews:

```powershell
python scripts\feed_broadcast.py --limit 2
python scripts\syndicate_guides.py --dry-run --max 2
python scripts\mastodon_from_feed.py --dry-run --force
python scripts\telegram_from_feed.py --dry-run
python scripts\social_bluesky_post.py --dry-run --force
python scripts\archive_save.py --dry-run
python scripts\pingomatic_ping.py --dry-run
python scripts\websub_publish.py --dry-run
```

### YouTube publishing

Local one-time authorization (select the **Sill Garden** identity in Google's chooser):

```powershell
python -m pip install -r requirements-youtube.txt
python scripts\youtube_oauth_login.py --force
python scripts\youtube_access_gate.py
python scripts\youtube_token_sync.py
```

Build/preview/upload one storyboard:

```powershell
python scripts\youtube_publish.py video-aerogarden-vs-click-grow --build --dry-run
python scripts\youtube_publish.py video-aerogarden-vs-click-grow --build --privacy public
```

The access gate requires the API channel title to be `Sill Garden`. Scheduled uploads are
**public** (one long-form video at 14:00 UTC and one Short at 09:00 UTC). Use
`youtube-publish-one.yml` for a manual one-off.

Sync OAuth from Maker Tool Stack after login:

```powershell
cd E:\Projects\makertoolstack
python scripts\google_token_sync.py
```

Manual runs:

```powershell
gh workflow run "Weekly analytics scorecard" -R nivco/sill-garden
gh workflow run "Traffic optimizer loop" -R nivco/sill-garden
gh workflow run "OAuth health check" -R nivco/sill-garden
```
