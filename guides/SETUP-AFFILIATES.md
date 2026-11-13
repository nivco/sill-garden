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

Partnership manager Kadri (Nov 2026) could not find the direct/Modash application and told this site to apply on **CJ**, advertiser **CID 4297609**. Do not resubmit the clickandgrow.com form.

- Apply: https://public.cj.com/signup/publisher?advertiserId=4297609
- Listed commission: 10% per sale. Direct-program cookie is 30 days; confirm the CJ offer before accepting.
- After CJ accepts the site, copy one deep link and set:
  - local `.env`: `PUBLIC_CLICK_GROW_AFFILIATE_URL=...`
  - GitHub secret: `PUBLIC_CLICK_GROW_AFFILIATE_URL`
- Until that link exists, Click & Grow cards stay on the tagged Amazon ASIN.
- The GitHub secret still holds an August placeholder (`clickandgrow.com/?ref=test-sill`), so
  `deploy.yml` no longer passes it to the build. After updating the secret to the CJ link,
  re-add the commented `PUBLIC_CLICK_GROW_AFFILIATE_URL` line in `.github/workflows/deploy.yml`.
- Reply in the same email thread with the site URL so she can match the CJ application.

### Gardener's Supply (second priority)

- Apply: https://www.gardeners.com/pages/partnership-program
- Network: Impact
- After approval, set `PUBLIC_GARDENERS_SUPPLY_AFFILIATE_URL=...`

GA4 records all sponsored clicks as `affiliate_click` with:
`affiliate_network`, `affiliate_merchant`, `affiliate_product`, `link_url`, and `page_path`.
