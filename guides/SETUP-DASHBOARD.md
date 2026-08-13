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

Open **http://127.0.0.1:8793/dashboard** → **Refresh**

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

4. **YouTube** (when you have a channel)  
   - `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_HANDLE`

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

### Secrets to set on `nivco/sill-garden`

Already needed for deploy: `CLOUDFLARE_*`, `PUBLIC_GA4_ID`

Also set (reuse MTS values where possible):

- `GOOGLE_USER_TOKEN_JSON` + `GOOGLE_OAUTH_CLIENT_JSON` (OAuth desktop token with Analytics + Search Console)
- `INDEXNOW_KEY` (same as local `.env` / `public/<key>.txt`)
- optional: `BING_WEBMASTER_API_KEY`, `CLOUDFLARE_API_TOKEN`, `YOUTUBE_*`

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
