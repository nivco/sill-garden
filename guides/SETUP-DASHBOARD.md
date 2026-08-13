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
