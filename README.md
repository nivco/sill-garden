# Sill Garden

Affiliate guide site for **windowsill and countertop gardens** in apartments.

- **Domain:** [sillgarden.com](https://sillgarden.com) (buy + point DNS when ready)
- **Stack:** [Astro](https://astro.build) → static → Cloudflare Pages
- **Niche:** quiet, compact, landlord-safe indoor growing (not outdoor farms / cannabis)

## Quick start

```bash
cd sill-garden
npm install
npm run dev
```

```bash
npm run build
npm run preview
```

## Project map

| Path | Purpose |
|------|---------|
| `src/content/guides/*.md` | All guides (frontmatter schema in `src/content.config.ts`) |
| `src/pages/` | Home, guides index, legal pages |
| `src/layouts/` | Base + guide article chrome |
| `src/lib/site.ts` | Brand, Amazon tag placeholder |
| `public/images/` | Hero + thumbs (swap for your own photos later) |

## Content frontmatter

- `cluster`: `systems` | `herbs` | `setup`
- `type`: `pillar` | `comparison` | `guide` | `howto` | `troubleshoot`
- `featured`: show on home
- `verdict`: quick-answer box
- `products`: optional list (URLs later = Amazon tagged links)

## Analytics dashboard (local)

```powershell
python scripts/analytics_summary.py
python scripts/dashboard_server.py
```

Open **http://127.0.0.1:8793/dashboard** — views, affiliate clicks, GSC, YouTube, Amazon. Setup: `guides/SETUP-DASHBOARD.md`.

## Launch checklist

1. ~~Buy **sillgarden.com**~~ · Pages project live at `sill-garden.pages.dev`
2. **DNS (do this now):** in [Cloudflare DNS for sillgarden.com](https://dash.cloudflare.com/867ff66d645bf10f3e97ae6c410415bd/sillgarden.com/dns/records) add:
   - `CNAME` · `@` · `sill-garden.pages.dev` · Proxied (orange cloud)
   - `CNAME` · `www` · `sill-garden.pages.dev` · Proxied (orange cloud)
3. Wait for Custom domains → `sillgarden.com` + `www` to show **Active** (SSL auto-provisions)
4. Apply to **Amazon Associates** with `https://sillgarden.com`
5. Put your tag in `src/lib/site.ts` → `amazonTag` and wire product URLs
6. Add GA4 + Search Console
7. Optional: GitHub Actions secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (`867ff66d645bf10f3e97ae6c410415bd`) so pushes to `main` auto-deploy

## Deploy (Cloudflare Pages)

**Live now**
- Preview: https://sill-garden.pages.dev
- Custom domains pending DNS CNAMEs above

**Option A — Dashboard (Git connect)**  
1. [Cloudflare Dashboard → Workers & Pages → sill-garden](https://dash.cloudflare.com/867ff66d645bf10f3e97ae6c410415bd/pages/view/sill-garden)  
2. Connect Git → **`nivco/sill-garden`**  
3. Build: `npm run build` · Output: `dist` · Node 22  

**Option B — GitHub Actions**  
Add repo secrets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`, then pushes to `main` deploy via `.github/workflows/deploy.yml`.

**Option C — Local**  
```bash
npx wrangler login
npm run build
npx wrangler pages deploy dist --project-name=sill-garden
```

## 90-day rhythm

2–3 new guides/week in the three clusters. Comparisons convert; setup guides build trust.

## License

Private project — all rights reserved.
