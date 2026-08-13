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

## Launch checklist

1. Buy **sillgarden.com** and attach to Cloudflare Pages
2. Apply to **Amazon Associates** with the live site URL
3. Put your tag in `src/lib/site.ts` → `amazonTag` and wire product URLs
4. Add GA4 + Search Console
5. Keep `/disclosure` and `/privacy` linked sitewide (already in layout)

## 90-day rhythm

2–3 new guides/week in the three clusters. Comparisons convert; setup guides build trust.

## License

Private project — all rights reserved.
