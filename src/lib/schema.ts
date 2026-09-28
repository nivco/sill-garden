import { site } from './site';

export type FaqItem = { question: string; answer: string };

/** Parse `## FAQ` bold-question blocks from guide markdown. */
export function parseFaqsFromMarkdown(body: string): FaqItem[] {
  const faqMatch = body.match(/##\s+FAQ\b([\s\S]*?)(?=\n##\s+|\n>\s*\*\*|$)/i);
  if (!faqMatch) return [];

  const section = faqMatch[1];
  const items: FaqItem[] = [];
  const re = /(?:^|\n)\*\*([^*\n]+?)\*\*\s*\n+([\s\S]*?)(?=(?:\n\*\*[^*\n]+?\*\*)|\n##\s|\n>\s|$)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(section)) !== null) {
    const rawQ = m[1].trim();
    if (/^key takeaway$/i.test(rawQ)) continue;
    const question = rawQ.replace(/\?*$/, '').trim() + '?';
    const answer = m[2]
      .split('\n')
      .filter((line) => !line.trim().startsWith('>'))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    if (question.length > 3 && answer.length > 20) {
      items.push({ question, answer });
    }
  }
  return items;
}

export function organizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: site.name,
    alternateName: ['SillGarden', 'sillgarden.com'],
    url: site.url,
    email: site.email,
    description: site.description,
    slogan: site.tagline,
    knowsAbout: [
      'indoor herb gardening',
      'countertop gardens',
      'windowsill herbs',
      'AeroGarden',
      'Click & Grow',
      'apartment gardening',
    ],
    disambiguatingDescription:
      'Sill Garden (sillgarden.com) is an independent apartment gardening guide site. It is not The Sill (thesill.com) and is not affiliated with that houseplant retailer.',
  };
}

export function websiteJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: site.name,
    url: site.url,
    description: site.description,
    publisher: {
      '@type': 'Organization',
      name: site.name,
      url: site.url,
    },
    inLanguage: 'en-US',
  };
}

export function faqPageJsonLd(faqs: FaqItem[]) {
  if (!faqs.length) return null;
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((f) => ({
      '@type': 'Question',
      name: f.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: f.answer,
      },
    })),
  };
}

export function articleJsonLd(opts: {
  title: string;
  description: string;
  url: string;
  image?: string;
  datePublished: string;
  dateModified?: string;
}) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: opts.title,
    description: opts.description,
    url: opts.url,
    image: opts.image ? [opts.image] : undefined,
    datePublished: opts.datePublished,
    dateModified: opts.dateModified || opts.datePublished,
    author: {
      '@type': 'Organization',
      name: site.name,
      url: site.url,
    },
    publisher: {
      '@type': 'Organization',
      name: site.name,
      url: site.url,
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': opts.url,
    },
  };
}
