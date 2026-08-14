export const site = {
  name: 'Sill Garden',
  domain: 'sillgarden.com',
  url: 'https://sillgarden.com',
  tagline: 'Grow on your sill — small space, real harvests.',
  description:
    'Practical guides to windowsill and countertop gardens for apartments: systems, herbs, setup, and honest product picks.',
  author: 'Sill Garden',
  email: 'hello@sillgarden.com',
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
