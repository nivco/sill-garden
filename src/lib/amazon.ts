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
};

/** Resolve the best affiliate href for a product pick. */
export function productHref(p: ProductLinkInput): string | undefined {
  if (p.url) return p.url;
  if (p.asin) return amazonDp(p.asin);
  if (p.search) return amazonSearch(p.search);
  if (site.amazonTag) return amazonSearch(p.name);
  return undefined;
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
