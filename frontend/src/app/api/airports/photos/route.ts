import { NextRequest, NextResponse } from "next/server";
import { searchOpenverseAirport } from "@/lib/photos/openverse";

export const runtime = "nodejs";

type PhotoMode = "airport" | "aircraft";

interface WikiImage {
  thumburl?: string;
  descriptionurl?: string;
  mime?: string;
  extmetadata?: Record<string, { value?: string }>;
}

interface WikiPage {
  title?: string;
  imageinfo?: WikiImage[];
}

interface WikiResponse {
  query?: {
    pages?: Record<string, WikiPage>;
  };
}

interface PhotoCandidate {
  image_url: string;
  source_url: string;
  title: string;
  license: string;
  credit: string;
  match_score: number;
}

const COMMONS_API = "https://commons.wikimedia.org/w/api.php";

const AIRPORT_TERMS = [
  "airport",
  "terminal",
  "runway",
  "apron",
  "airfield",
  "airside",
  "concourse",
  "aerial",
  "tower",
  "taxiway",
  "control tower",
];

const EXCLUDED_TERMS = [
  "cargo container",
  "cargo pallet",
  "baggage cart",
  "boarding pass",
  "boarding ticket",
  "scale model",
  "model aircraft",
  "diagram",
  "chart",
  "schematic",
  "illustration",
  "blueprint",
  "floor plan",
  "route map",
  "aircraft cabin",
  "cockpit interior",
  "airline meal",
];

const AIRCRAFT_TERMS: Record<string, string[]> = {
  A388: ["a380", "a380-800"],
  A359: ["a350", "a350-900"],
  A35K: ["a350-1000"],
  A333: ["a330", "a330-300"],
  A343: ["a340-300"],
  A346: ["a340-600"],
  B77W: ["777-300er", "b777-300er"],
  B772: ["777-200", "b777-200"],
  B38M: ["737 max 8", "737-8 max", "737-8"],
  B738: ["737-800"],
  A320: ["a320"],
  A321: ["a321"],
  A319: ["a319"],
};

const AIRLINE_TERMS = [
  "lufthansa",
  "emirates",
  "united airlines",
  "qatar airways",
  "british airways",
  "qantas",
  "singapore airlines",
  "cathay pacific",
  "air france",
  "klm",
  "etihad",
  "turkish airlines",
  "delta",
  "american airlines",
];

function clean(value: string): string {
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function compact(value: string): string {
  return normalize(value).replace(/\s+/g, "");
}

function containsPhrase(text: string, phrase: string): boolean {
  return compact(text).includes(compact(phrase));
}

function airportKeywords(name: string): string[] {
  const stopWords = new Set([
    "airport",
    "international",
    "terminal",
    "the",
    "of",
    "and",
    "city",
  ]);

  return normalize(name)
    .split(" ")
    .filter((word) => word.length >= 4 && !stopWords.has(word));
}

function acceptableLicense(
  metadata: Record<string, { value?: string }>,
): string | null {
  const license = clean(metadata.LicenseShortName?.value || "");

  const licenseUrl = clean(metadata.LicenseUrl?.value || "");

  const accepted = ["CC0", "CC BY", "CC BY-SA", "PUBLIC DOMAIN", "PDM"];

  const normalized = license.toUpperCase();

  const allowed = accepted.some(
    (value) => normalized === value || normalized.startsWith(`${value} `),
  );

  const validUrl =
    /creativecommons\.org\/licenses\/by(?:-sa)?\//i.test(licenseUrl) ||
    /creativecommons\.org\/publicdomain\//i.test(licenseUrl);

  return allowed || validUrl ? license : null;
}

function isExcluded(title: string): boolean {
  return EXCLUDED_TERMS.some((term) => containsPhrase(title, term));
}

function scoreAirportPhoto(
  title: string,
  code: string,
  airportName: string,
): number {
  const normalized = normalize(title);

  if (isExcluded(title)) {
    return -1;
  }

  const codeMatch = new RegExp(`(^|\\s)${code.toLowerCase()}(\\s|$)`).test(
    normalized,
  );

  const words = airportKeywords(airportName);

  const nameMatches = words.filter((word) => normalized.includes(word));

  if (!codeMatch && nameMatches.length === 0) {
    return -1;
  }

  const hasAirportSubject = AIRPORT_TERMS.some((term) =>
    containsPhrase(title, term),
  );

  if (!hasAirportSubject) {
    return -1;
  }

  // Avoid airline/aircraft portraits appearing
  // as destination airport photography.
  const hasAirline = AIRLINE_TERMS.some((airline) =>
    containsPhrase(title, airline),
  );

  const hasAircraftManufacturer =
    /\b(airbus|boeing|embraer|bombardier)\b/i.test(title);

  if (hasAirline || hasAircraftManufacturer) {
    return -1;
  }

  let score = 0;

  if (codeMatch) score += 60;

  score += Math.min(nameMatches.length, 2) * 20;

  if (normalized.includes("terminal")) score += 30;
  if (normalized.includes("aerial")) score += 25;
  if (normalized.includes("runway")) score += 25;
  if (normalized.includes("apron")) score += 15;
  if (normalized.includes("taxiway")) score += 10;
  if (normalized.includes("airport")) score += 10;

  return score;
}

function scoreAircraftPhoto(
  title: string,
  airline: string,
  aircraftCode: string,
  destinationCode: string,
): number {
  const types = AIRCRAFT_TERMS[aircraftCode];

  if (!types?.length) return -1;

  if (isExcluded(title)) return -1;

  if (!containsPhrase(title, airline)) {
    return -1;
  }

  if (!types.some((type) => containsPhrase(title, type))) {
    return -1;
  }

  let score = 85;

  if (containsPhrase(title, destinationCode)) {
    score += 30;
  }

  if (/\b(landing|takeoff|taxi|approach|airport)\b/i.test(title)) {
    score += 10;
  }

  return score;
}

async function searchCommons(search: string): Promise<WikiPage[]> {
  const params = new URLSearchParams({
    action: "query",
    format: "json",
    generator: "search",
    gsrsearch: `filetype:bitmap ${search}`,
    gsrnamespace: "6",
    gsrlimit: "35",
    prop: "imageinfo",
    iiprop: "url|mime|extmetadata",
    iiurlwidth: "1200",
    iiextmetadatafilter: "LicenseShortName|LicenseUrl|Copyrighted|Artist",
  });

  const userAgent = process.env.COMMONS_USER_AGENT;

  const response = await fetch(`${COMMONS_API}?${params.toString()}`, {
    headers: {
      ...(userAgent ? { "User-Agent": userAgent } : {}),
      Accept: "application/json",
    },
    next: {
      revalidate: 86400,
    },
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    throw new Error(`Wikimedia Commons returned HTTP ${response.status}`);
  }

  const data = (await response.json()) as WikiResponse;

  return Object.values(data.query?.pages || {});
}

async function getCommonsPhoto(
  code: string,
  name: string,
  mode: PhotoMode,
  airline: string,
  aircraftCode: string,
): Promise<PhotoCandidate | null> {
  const searches =
    mode === "airport"
      ? [
          `${code} airport terminal`,
          `${name || code} airport aerial`,
          `${name || code} airport runway`,
        ]
      : [
          `${airline} ${AIRCRAFT_TERMS[aircraftCode][0]} ${code}`,
          `${airline} ${AIRCRAFT_TERMS[aircraftCode][0]} aircraft`,
        ];

  const candidates: PhotoCandidate[] = [];

  let successfulSearches = 0;

  for (const search of searches) {
    let pages: WikiPage[];

    try {
      pages = await searchCommons(search);
      successfulSearches++;
    } catch (error) {
      console.warn(`[Airport Photos] Commons search failed: ${search}`, error);

      // Don't abort other search variations.
      continue;
    }

    for (const page of pages) {
      const image = page.imageinfo?.[0];

      if (!image?.thumburl || !image.descriptionurl || !page.title) {
        continue;
      }

      if (
        !["image/jpeg", "image/png", "image/webp"].includes(image.mime || "")
      ) {
        continue;
      }

      const metadata = image.extmetadata || {};
      const license = acceptableLicense(metadata);

      if (!license) continue;

      const score =
        mode === "airport"
          ? scoreAirportPhoto(page.title, code, name)
          : scoreAircraftPhoto(page.title, airline, aircraftCode, code);

      if (score < 0) continue;

      candidates.push({
        image_url: image.thumburl,
        source_url: image.descriptionurl,
        title: page.title,
        license,
        credit: clean(metadata.Artist?.value || "Unknown creator"),
        match_score: score,
      });
    }
  }

  // Remove duplicate files across search variations.
  const unique = Array.from(
    new Map(
      candidates.map((candidate) => [candidate.source_url, candidate]),
    ).values(),
  );

  unique.sort((a, b) => b.match_score - a.match_score);

  console.info(
    `[Airport Photos] ${code}: ${successfulSearches}/${searches.length} ` +
      `Commons searches succeeded, ${unique.length} candidates`,
  );

  return unique[0] || null;
}

async function getOpenverseFallback(
  code: string,
  name: string,
): Promise<ReturnType<typeof NextResponse.json>> {
  try {
    const alternative = await searchOpenverseAirport(code, name);

    if (alternative?.image_url) {
      console.info(`[Airport Photos] ${code}: Openverse fallback selected`);

      return NextResponse.json({
        ...alternative,
        airport_code: code,
        mode: "airport",
        source: "Openverse",
        photo_confidence:
          (alternative.match_score || 0) >= 90 ? "high" : "medium",
      });
    }
  } catch (error) {
    console.warn(
      `[Airport Photos] Openverse fallback failed for ${code}`,
      error,
    );
  }

  return NextResponse.json({
    airport_code: code,
    mode: "airport",
    image_url: null,
    source: null,
    reason: "No sufficiently relevant public-domain airport image found.",
  });
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const code = (params.get("code") || "").trim().toUpperCase();

  const name = (params.get("name") || "").trim();

  const mode: PhotoMode =
    params.get("mode") === "aircraft" ? "aircraft" : "airport";

  const airline = (params.get("airline") || "").trim();

  const aircraftCode = (params.get("aircraft") || "").trim().toUpperCase();

  if (!/^[A-Z0-9]{4}$/.test(code)) {
    return NextResponse.json(
      {
        detail: "Invalid ICAO airport code.",
      },
      {
        status: 400,
      },
    );
  }

  if (mode === "aircraft") {
    if (!airline || !AIRCRAFT_TERMS[aircraftCode]) {
      return NextResponse.json({
        airport_code: code,
        mode,
        image_url: null,
        reason: "Verified airline and aircraft type are required.",
      });
    }
  }

  // Primary source: Wikimedia Commons.
  let commonsPhoto: PhotoCandidate | null = null;

  try {
    commonsPhoto = await getCommonsPhoto(
      code,
      name,
      mode,
      airline,
      aircraftCode,
    );
  } catch (error) {
    console.error(
      `[Airport Photos] Unexpected Commons failure for ${code}`,
      error,
    );
  }

  if (commonsPhoto) {
    return NextResponse.json({
      airport_code: code,
      mode,
      source: "Wikimedia Commons",
      ...commonsPhoto,
      photo_confidence: commonsPhoto.match_score >= 100 ? "high" : "medium",
    });
  }

  // Secondary source: Openverse.
  // Currently only supports airport photography.
  if (mode === "airport") {
    return getOpenverseFallback(code, name);
  }

  // Never substitute a random airline or aircraft
  // when an exact aircraft match is unavailable.
  return NextResponse.json({
    airport_code: code,
    mode,
    image_url: null,
    source: null,
    reason: "No matching public-domain airline/aircraft image found.",
  });
}
