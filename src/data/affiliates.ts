/**
 * Canonical Amazon / partner affiliate picks for Sill Garden.
 * Prefer stable ASINs; fall back to search when listings churn.
 * Monetize physical gear only — not AI-spittable digital products.
 */
export type AffiliateProduct = {
  id: string;
  name: string;
  note: string;
  asin?: string;
  search?: string;
  partner?: 'amazon' | 'click-grow' | 'gardeners-supply';
};

export const affiliateProducts = {
  aerogardenHarvest: {
    id: 'aerogarden-harvest',
    name: 'AeroGarden Harvest (6-pod class)',
    note: 'Best default starter for most kitchens',
    asin: 'B07CKNWHPQ',
  },
  clickAndGrow3: {
    id: 'click-and-grow-3',
    name: 'Click & Grow Smart Garden 3',
    note: 'Silent wick system — studio-friendly',
    asin: 'B01MRVMKQH',
    partner: 'click-grow',
  },
  budget12Pod: {
    id: 'budget-12-pod',
    name: 'Budget 10–12 pod kits (iDOO / similar)',
    note: 'More plants per dollar; check pump noise reviews',
    search: 'iDOO hydroponics 12 pod indoor garden',
  },
  kratkyJar: {
    id: 'kratky-jar',
    name: 'Kratky mason jar setup',
    note: 'Silent DIY; pair with a clip light if the sill is dim',
    search: 'Kratky hydroponic mason jar kit',
  },
  clipGrowLight: {
    id: 'clip-grow-light',
    name: 'Clip-on LED grow light',
    note: 'Cheap fix for dim sills and soil pots',
    search: 'LED clip grow light indoor plants',
  },
  outletTimer: {
    id: 'outlet-timer',
    name: '24-hour outlet timer',
    note: 'Set light on/off without an app',
    search: '24 hour mechanical outlet timer',
  },
  basilSeeds: {
    id: 'basil-seeds',
    name: 'Genovese basil seeds',
    note: 'After one branded pod cycle, grow what you cook',
    search: 'Genovese basil seeds for planting',
  },
  mintSeeds: {
    id: 'mint-seeds',
    name: 'Spearmint seeds',
    note: 'Forgiving apartment herb once you leave branded pods',
    search: 'spearmint seeds for planting',
  },
  bootTray: {
    id: 'boot-tray',
    name: 'Waterproof boot / drip tray',
    note: 'Landlord-safe under reservoirs and pots',
    search: 'waterproof boot tray for plants',
  },
  herbPots: {
    id: 'herb-pots',
    name: 'Small herb pots with saucers',
    note: 'Windowsill set without a hydro kit',
    search: 'herb pots with saucers indoor',
  },
  aerogardenSponges: {
    id: 'aerogarden-sponges',
    name: 'AeroGarden grow sponges / blank pods',
    note: 'Cut refill cost after cycle one',
    search: 'AeroGarden grow sponges blank pods',
  },
  clickGrowRefills: {
    id: 'click-grow-refills',
    name: 'Click & Grow plant pods / refills',
    note: 'Branded pods for the first harvest',
    search: 'Click and Grow plant pods refill',
    partner: 'click-grow',
  },
  clickGrowCompatible: {
    id: 'click-grow-compatible',
    name: 'Click & Grow compatible blank inserts',
    note: 'Use your own seed after you know what you eat',
    search: 'Click and Grow compatible pods blank',
  },
  liquidPlantFood: {
    id: 'liquid-plant-food',
    name: 'Indoor herb / hydro plant food',
    note: 'Needed for blank pods and Kratky jars',
    search: 'indoor hydroponic plant food nutrients',
  },
  bambooLightHood: {
    id: 'bamboo-light-hood',
    name: 'Desk / light privacy screen',
    note: 'Cuts LED bleed in studios near a bed',
    search: 'bamboo desk privacy panel small',
  },
  pottingMix: {
    id: 'potting-mix',
    name: 'Light potting mix (not garden soil)',
    note: 'For sill pots — drainage matters in rentals',
    search: 'indoor potting mix for herbs',
  },
} as const satisfies Record<string, AffiliateProduct>;

export type AffiliateProductId = keyof typeof affiliateProducts;

/** Map catalog entries into guide frontmatter-shaped product picks. */
export function picks(...ids: AffiliateProductId[]) {
  return ids.map((id) => {
    const p = affiliateProducts[id];
    return {
      name: p.name,
      note: p.note,
      ...(p.asin ? { asin: p.asin } : {}),
      ...(p.search ? { search: p.search } : {}),
      ...('partner' in p && p.partner ? { partner: p.partner } : {}),
    };
  });
}

export function productById(id: AffiliateProductId): AffiliateProduct {
  return affiliateProducts[id];
}
