import { affiliateProducts, type AffiliateProductId } from './affiliates';

export type StarterKit = {
  slug: string;
  title: string;
  eyebrow: string;
  description: string;
  whoFor: string;
  primaryId: AffiliateProductId;
  stackIds: AffiliateProductId[];
  guideHref: string;
  guideLabel: string;
  yearOneNote: string;
};

/** Physical starter stacks — not digital products AI can regenerate. */
export const starterKits: StarterKit[] = [
  {
    slug: 'studio-silence',
    title: 'Studio Silence Kit',
    eyebrow: 'Sleep in the same room',
    description:
      'No-pump countertop garden plus the landlord-safe extras that stop water and light from wrecking a studio.',
    whoFor: 'Open studios, light sleepers, bedrooms that share the kitchen.',
    primaryId: 'clickAndGrow3',
    stackIds: ['clickAndGrow3', 'bootTray', 'bambooLightHood', 'clickGrowRefills', 'outletTimer'],
    guideHref: '/guides/quiet-countertop-gardens-studios/',
    guideLabel: 'Quiet gardens guide',
    yearOneNote:
      'Hardware once + branded pods early, then blanks. Expect accessories (tray / shade) to matter as much as the kit in a studio.',
  },
  {
    slug: 'kitchen-capacity',
    title: 'Kitchen Capacity Kit',
    eyebrow: 'Separate kitchen counter',
    description:
      'Harvest-class kit for cooks who use basil and mint weekly — plus blanks and seeds so month two does not empty the wallet.',
    whoFor: '1-beds with a real kitchen corner and a soft pump hum is fine.',
    primaryId: 'aerogardenHarvest',
    stackIds: ['aerogardenHarvest', 'bootTray', 'aerogardenSponges', 'basilSeeds', 'liquidPlantFood'],
    guideHref: '/guides/aerogarden-vs-click-and-grow/',
    guideLabel: 'AeroGarden vs Click & Grow',
    yearOneNote:
      'Buy branded pods for cycle one only. Blanks + Genovese seed is where ongoing cost drops.',
  },
  {
    slug: 'under-50',
    title: 'Under-$50 Sill Kit',
    eyebrow: 'Budget / cheap / simple',
    description:
      'Pots, tray, seeds, and a clip light — the cheap, compact, waterproof-tray path for “best herb garden under $50” searches when daylight is decent or you will add one lamp.',
    whoFor:
      'Bright sills, renters testing the habit before a $100 kit, and anyone who wants simple/natural soil herbs without pods.',
    primaryId: 'herbPots',
    stackIds: ['herbPots', 'bootTray', 'pottingMix', 'basilSeeds', 'clipGrowLight'],
    guideHref: '/guides/cheapest-indoor-herb-garden-apartment/',
    guideLabel: 'Cheapest apartment herb garden',
    yearOneNote:
      'Skip branded pods entirely. Your recurring spend is seeds, mix top-ups, and electricity for the clip light.',
  },
  {
    slug: 'homemade-kratky',
    title: 'Homemade Kratky Kit',
    eyebrow: 'Homemade / quiet DIY',
    description:
      'Mason-jar Kratky, tray, nutrients, seeds, and a clip light — the homemade silent lane under ~$50 when you want jars instead of soil pots.',
    whoFor:
      'Studios that need zero pump noise, tinkerers, and “best homemade herb garden under 50” shoppers with honest light.',
    primaryId: 'kratkyJar',
    stackIds: ['kratkyJar', 'bootTray', 'liquidPlantFood', 'basilSeeds', 'clipGrowLight'],
    guideHref: '/guides/kratky-jar-herbs-apartment/',
    guideLabel: 'Kratky jar herbs guide',
    yearOneNote:
      'No branded pods. Recurring cost is nutrient solution, seed, and clip-light electricity. Replace jars only if seals fail.',
  },
];

export function kitBySlug(slug: string): StarterKit | undefined {
  return starterKits.find((k) => k.slug === slug);
}

export function kitProducts(kit: StarterKit) {
  return kit.stackIds.map((id) => affiliateProducts[id]);
}

export type RefillGroup = {
  title: string;
  blurb: string;
  productIds: AffiliateProductId[];
};

export const refillGroups: RefillGroup[] = [
  {
    title: 'AeroGarden lane',
    blurb: 'After Harvest-class cycle one, blanks + seed beat buying another gourmet pod pack.',
    productIds: ['aerogardenSponges', 'basilSeeds', 'mintSeeds', 'liquidPlantFood'],
  },
  {
    title: 'Click & Grow lane',
    blurb: 'Start with branded pods so hardware and seed aren’t debugging together — then move to compatible blanks.',
    productIds: ['clickGrowRefills', 'clickGrowCompatible', 'basilSeeds', 'liquidPlantFood'],
  },
  {
    title: 'Soil / sill lane',
    blurb: 'No pods. Recurring cost is mix, seeds, and saucers that protect the deposit.',
    productIds: ['herbPots', 'pottingMix', 'basilSeeds', 'mintSeeds', 'bootTray'],
  },
];
