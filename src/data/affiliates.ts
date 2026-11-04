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
  aerogardenBounty: {
    id: 'aerogarden-bounty',
    name: 'AeroGarden Bounty (9-pod class)',
    note: 'Deeper counter, taller plants — confirm the exact listing is in stock',
    search: 'AeroGarden Bounty indoor garden',
  },
  aerogardenHarvestElite: {
    id: 'aerogarden-harvest-elite',
    name: 'AeroGarden Harvest Elite',
    note: 'Same pod count as Harvest, taller light arm',
    search: 'AeroGarden Harvest Elite',
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
  wideMouthJars: {
    id: 'wide-mouth-jars',
    name: 'Wide-mouth mason jars',
    note: 'Clear jars so you can see the Kratky water line',
    search: 'wide mouth mason jars 32 oz',
  },
  netPots: {
    id: 'net-pots',
    name: 'Hydroponic net pots',
    note: '3-inch cups that sit in a jar lid',
    search: '3 inch hydroponic net pots',
  },
  clayPebbles: {
    id: 'clay-pebbles',
    name: 'Clay pebbles (hydroton)',
    note: 'Holds the stem in a net pot without soil',
    search: 'hydroton clay pebbles',
  },
  phStrips: {
    id: 'ph-strips',
    name: 'Hydroponic pH test strips',
    note: 'Check nutrient water before you blame the seed',
    search: 'hydroponic pH test strips',
  },
  parsleySeeds: {
    id: 'parsley-seeds',
    name: 'Italian parsley seeds',
    note: 'Slower than basil; worth a bright sill or a clip light',
    search: 'Italian parsley seeds for planting',
  },
  cilantroSeeds: {
    id: 'cilantro-seeds',
    name: 'Cilantro seeds',
    note: 'Bolts in heat — harvest leaves early',
    search: 'cilantro coriander seeds for planting',
  },
  chivesSeeds: {
    id: 'chives-seeds',
    name: 'Chive seeds',
    note: 'Forgiving on a weaker apartment sill',
    search: 'chive seeds for planting',
  },
  lettuceSeeds: {
    id: 'lettuce-seeds',
    name: 'Loose-leaf lettuce seeds',
    note: 'Easier first Kratky crop than woody herbs',
    search: 'loose leaf lettuce seeds hydroponic',
  },
  herbSnips: {
    id: 'herb-snips',
    name: 'Herb snips',
    note: 'Pinch harvests without tearing stems',
    search: 'herb scissors kitchen',
  },
  daylightBulb: {
    id: 'daylight-bulb',
    name: '6500K daylight LED bulb',
    note: 'Desk-lamp upgrade when a clip light is too small',
    search: '6500K LED grow light bulb',
  },
  cocoCoir: {
    id: 'coco-coir',
    name: 'Coco coir for seed starting',
    note: 'Light medium for pots — not backyard dirt',
    search: 'coco coir seed starting bricks',
  },
  surgeStrip: {
    id: 'surge-strip',
    name: 'Surge-protected power strip',
    note: 'Lights, pumps, and timers on one protected outlet',
    search: 'surge protector power strip',
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
