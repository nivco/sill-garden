import { site } from './site';

/** Product detail page with Associates tag. */
export function amazonDp(asin: string): string {
  const tag = site.amazonTag;
  const base = `https://www.amazon.com/dp/${asin}`;
  return tag ? `${base}?tag=${encodeURIComponent(tag)}` : base;
}

/** Search results with Associates tag (good when ASIN churns). */
export function amazonSearch(query: string): string {
  const tag = site.amazonTag;
  const base = `https://www.amazon.com/s?k=${encodeURIComponent(query)}`;
  return tag ? `${base}&tag=${encodeURIComponent(tag)}` : base;
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
