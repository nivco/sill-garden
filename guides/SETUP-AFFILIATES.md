# Amazon Associates setup (Sill Garden)

## What’s wired in code

- Store ID / tag: **`sillgarden09-20`** in `src/lib/site.ts`
- Link builders: `src/lib/amazon.ts` (`amazonDp`, `amazonSearch`, `productHref`)
- Product catalog: `src/data/affiliates.ts`
- Guide CTAs: every guide frontmatter `products:` → “Check price on Amazon” with `rel="nofollow sponsored"`
- GA4: `affiliate_click` on Amazon / sponsored outbound links (`BaseLayout.astro`)
- Disclosure: `/disclosure/` + footer on guides

## Associates Central checklist

1. [Associates Central](https://affiliate-program.amazon.com/) → account approved for **amazon.com**
2. **Account settings → Websites / Mobile apps** → add `https://sillgarden.com` (and `www`)
3. Confirm tracking ID **`sillgarden09-20`** (or create it and update `site.amazonTag`)
4. Test: open any guide CTA → URL must include `tag=sillgarden09-20`
5. Wait for first attributed click/order in **Reports** (can take 24–48h)

## YouTube / social

When you publish a video, paste tagged deep links from Associates SiteStripe **or** reuse:

```
https://www.amazon.com/dp/B07CKNWHPQ?tag=sillgarden09-20&linkCode=ll1
https://www.amazon.com/dp/B01MRVMKQH?tag=sillgarden09-20&linkCode=ll1
```

Always include the affiliate disclosure in the description.

## Earnings on the dashboard

Amazon has no public API. Weekly paste into `products/analytics/amazon-manual.json`.

## Direct programs

Direct programs override Amazon for matching products after their approved URL is configured.
Until then, the product card safely falls back to the tagged Amazon link.

### Click & Grow (first priority)

- Apply: https://www.clickandgrow.com/pages/affiliate-program
- Published terms: 10%+ commission, 45-day tracking, monthly PayPal payout
- After approval, set the complete tracking/deep link as:
  - local `.env`: `PUBLIC_CLICK_GROW_AFFILIATE_URL=...`
  - GitHub secret: `PUBLIC_CLICK_GROW_AFFILIATE_URL`
- Used by three relevant guides.

### Gardener's Supply (second priority)

- Apply: https://www.gardeners.com/pages/partnership-program
- Network: Impact
- After approval, set `PUBLIC_GARDENERS_SUPPLY_AFFILIATE_URL=...`

GA4 records all sponsored clicks as `affiliate_click` with:
`affiliate_network`, `affiliate_merchant`, `affiliate_product`, `link_url`, and `page_path`.
