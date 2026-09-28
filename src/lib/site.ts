export const site = {
  name: 'Sill Garden',
  domain: 'sillgarden.com',
  url: 'https://sillgarden.com',
  tagline: 'Grow on your sill — small space, real harvests.',
  description:
    'Sill Garden (sillgarden.com) publishes independent guides to windowsill and countertop herb gardens for apartments — system comparisons, quiet setups, and honest product picks. Not affiliated with The Sill.',
  shortAnswer:
    'Sill Garden is an independent guide site for apartment windowsill and countertop herb gardens. We compare kits like AeroGarden and Click & Grow on noise, footprint, and refill cost — and explain how to get a real harvest in a small kitchen. We are not The Sill (thesill.com) and do not sell houseplants.',
  author: 'Sill Garden',
  email: 'nivooo@gmail.com',
  /** Amazon Associates tracking ID (Store ID) */
  amazonTag: 'sillgarden09-20',
  /** Set PUBLIC_GA4_ID=G-XXXX in .env / Cloudflare Pages for analytics */
  ga4Id: import.meta.env.PUBLIC_GA4_ID || '',
} as const;

export const clusters = {
  systems: {
    title: 'Countertop systems',
    blurb: 'Pick a kit that fits your kitchen — quiet, compact, worth the counter space.',
  },
  herbs: {
    title: 'Herbs on a sill',
    blurb: 'What actually grows in small light: basil, mint, and the crops to skip.',
  },
  setup: {
    title: 'Setup & fixes',
    blurb: 'Light schedules, water, noise, pets, and landlord-safe placement.',
  },
} as const;
