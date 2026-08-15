import { site } from './site';

/** Product detail page with Associates tag. */
export function amazonDp(asin: string, linkCode = 'll1'): string {
  const tag = site.amazonTag;
  const params = new URLSearchParams();
  if (tag) params.set('tag', tag);
  if (linkCode) params.set('linkCode', linkCode);
  const q = params.toString();
  return q ? `https://www.amazon.com/dp/${asin}?${q}` : `https://www.amazon.com/dp/${asin}`;
}

/** Search results with Associates tag (good when ASIN churns). */
export function amazonSearch(query: string, linkCode = 'll2'): string {
  const tag = site.amazonTag;
  const params = new URLSearchParams();
  params.set('k', query);
  if (tag) params.set('tag', tag);
  if (linkCode) params.set('linkCode', linkCode);
  return `https://www.amazon.com/s?${params.toString()}`;
}

export type ProductLinkInput = {
  name: string;
  url?: string;
  asin?: string;
  search?: string;
  partner?: 'amazon' | 'click-grow' | 'gardeners-supply';
};

export type ResolvedProductLink = {
  href?: string;
  merchant: string;
  network: string;
};

const directPartnerUrls = {
  'click-grow': import.meta.env.PUBLIC_CLICK_GROW_AFFILIATE_URL || '',
  'gardeners-supply': import.meta.env.PUBLIC_GARDENERS_SUPPLY_AFFILIATE_URL || '',
} as const;

const partnerLabels = {
  amazon: 'Amazon',
  'click-grow': 'Click & Grow',
  'gardeners-supply': "Gardener's Supply",
} as const;

/** Prefer an approved direct program; fall back to the tagged Amazon link. */
export function productLink(p: ProductLinkInput): ResolvedProductLink {
  if (p.url) {
    return {
      href: p.url,
      merchant: p.partner ? partnerLabels[p.partner] : 'Partner store',
      network: p.partner || 'direct',
    };
  }

  if (p.partner && p.partner !== 'amazon') {
    const directUrl = directPartnerUrls[p.partner];
    if (directUrl) {
      return {
        href: directUrl,
        merchant: partnerLabels[p.partner],
        network: p.partner,
      };
    }
  }

  const href = p.asin
    ? amazonDp(p.asin)
    : p.search
      ? amazonSearch(p.search)
      : site.amazonTag
        ? amazonSearch(p.name)
        : undefined;

  return { href, merchant: 'Amazon', network: 'amazon-associates' };
}

/** Backwards-compatible href-only resolver. */
export function productHref(p: ProductLinkInput): string | undefined {
  return productLink(p).href;
}

/** Plain tagged links for YouTube / social descriptions (no HTML). */
export function affiliateLines(
  items: Array<{ label: string; asin?: string; search?: string }>,
): string {
  return items
    .map((item) => {
      const href = item.asin
        ? amazonDp(item.asin)
        : item.search
          ? amazonSearch(item.search)
          : amazonSearch(item.label);
      return `• ${item.label}: ${href}`;
    })
    .join('\n');
}
