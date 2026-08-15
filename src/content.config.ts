import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const guides = defineCollection({
  loader: glob({ base: './src/content/guides', pattern: '**/*.md' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    cluster: z.enum(['systems', 'herbs', 'setup']),
    type: z.enum(['pillar', 'comparison', 'guide', 'howto', 'troubleshoot']),
    featured: z.boolean().default(false),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    verdict: z.string().optional(),
    products: z
      .array(
        z.object({
          name: z.string(),
          note: z.string().optional(),
          url: z.string().url().optional(),
          asin: z.string().optional(),
          search: z.string().optional(),
          partner: z.enum(['amazon', 'click-grow', 'gardeners-supply']).optional(),
        }),
      )
      .optional(),
  }),
});

export const collections = { guides };
