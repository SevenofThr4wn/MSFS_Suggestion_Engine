import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

type MatchType = "registration" | "airline_aircraft" | "aircraft_type" | "none";

interface PhotoResult {
  image_url: string | null;
  source_url: string | null;
  source: string | null;
  title: string | null;
  credit: string | null;
  license: string | null;
  license_url: string | null;
  match_type: MatchType;
  matched_registration: string | null;
  confidence: "high" | "medium" | "none";
  reason?: string;
}

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

interface AircraftDefinition {
  searches: string[];
  patterns: RegExp[];
}

const AIRCRAFT: Record<string, AircraftDefinition> = {
  A388: {
    searches: ["Airbus A380-800", "Airbus A380"],
    patterns: [/\bA380(?:[- ]800)?\b/i],
  },
  A359: {
    searches: ["Airbus A350-900"],
    patterns: [/\bA350[- ]900\b/i],
  },
  A35K: {
    searches: ["Airbus A350-1000"],
    patterns: [/\bA350[- ]1000\b/i],
  },
  A333: {
    searches: ["Airbus A330-300"],
    patterns: [/\bA330[- ]300\b/i],
  },
  A343: {
    searches: ["Airbus A340-300"],
    patterns: [/\bA340[- ]300\b/i],
  },
  A346: {
    searches: ["Airbus A340-600"],
    patterns: [/\bA340[- ]600\b/i],
  },
  B77W: {
    searches: ["Boeing 777-300ER"],
    patterns: [/\b777[- ]300ER\b/i, /\bB77W\b/i],
  },
  B77L: {
    searches: ["Boeing 777-200LR"],
    patterns: [/\b777[- ]200LR\b/i, /\bB77L\b/i],
  },
  B772: {
    searches: ["Boeing 777-200ER", "Boeing 777-200"],
    patterns: [/\b777[- ]200ER\b/i, /\b777[- ]200\b(?!\s*LR)/i, /\bB772\b/i],
  },
  B738: {
    searches: ["Boeing 737-800"],
    patterns: [/\b737[- ]800\b/i],
  },
  B38M: {
    searches: ["Boeing 737 MAX 8"],
    patterns: [
      /\b737[- ]MAX[- ]8\b/i,
      /\b737[- ]8[- ]MAX\b/i,
      /\b737[- ]8\b/i,
      /\bB38M\b/i,
    ],
  },
  A319: {
    searches: ["Airbus A319"],
    patterns: [/\bA319\b/i],
  },
  A320: {
    searches: ["Airbus A320"],
    patterns: [/\bA320\b/i],
  },
  A321: {
    searches: ["Airbus A321"],
    patterns: [/\bA321\b/i],
  },
};

const COMMONS_API = "https://commons.wikimedia.org/w/api.php";

const REJECTED_SUBJECTS = [
  /\bdiagram\b/i,
  /\bchart\b/i,
  /\bschematic\b/i,
  /\bblueprint\b/i,
  /\billustration\b/i,
  /\bscale model\b/i,
  /\bflight simulator\b/i,
  /\bcockpit interior\b/i,
  /\bseat map\b/i,
  /\bcargo container\b/i,
  /\bairport map\b/i,
];

function normalize(value: string): string {
  return value
    .normalize("NFKD")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, " ")
    .trim();
}

function stripHtml(value: string): string {
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&nbsp;/gi, " ")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function matchesPhrase(text: string, phrase: string): boolean {
  const normalized = normalize(text);
  const expected = normalize(phrase);

  return !!expected && ` ${normalized} `.includes(` ${expected} `);
}

function matchesRegistration(text: string, registration: string): boolean {
  const value = normalize(registration);
  const normalizedText = normalize(text);

  if (` ${normalizedText} `.includes(` ${value} `)) {
    return true;
  }

  // Some filenames omit the registration hyphen.
  const compactRegistration = value.replace(/\s/g, "");

  return normalizedText.split(" ").includes(compactRegistration);
}

function matchesType(title: string, code: string): boolean {
  const definition = AIRCRAFT[code];

  if (!definition) return false;

  const text = title.replace(/^File:/i, "").replace(/_/g, " ");

  // Reject explicitly identified conflicting variants.
  const conflictingVariants: Record<string, RegExp[]> = {
    A359: [/\bA350[- ]1000\b/i],
    A35K: [/\bA350[- ]900\b/i],
    A343: [/\bA340[- ]600\b/i],
    A346: [/\bA340[- ]300\b/i],
    B77W: [/\b777[- ]200(?:ER|LR)?\b/i],
    B77L: [/\b777[- ]300(?:ER)?\b/i],
    B772: [/\b777[- ]200LR\b/i],
    B738: [/\b737[- ](?:MAX[- ]?8|8[- ]MAX)\b/i],
    B38M: [/\b737[- ]800\b/i],
  };

  if (conflictingVariants[code]?.some((pattern) => pattern.test(text))) {
    return false;
  }

  return definition.patterns.some((pattern) => pattern.test(text));
}

function validLicense(
  metadata: Record<string, { value?: string }>,
): { name: string; url: string | null } | null {
  const name = stripHtml(metadata.LicenseShortName?.value || "");

  const url = stripHtml(metadata.LicenseUrl?.value || "");

  const copyrighted = stripHtml(
    metadata.Copyrighted?.value || "",
  ).toLowerCase();

  const normalized = name.toUpperCase();

  const cc0 =
    /^CC0(?:\s|$)/.test(normalized) ||
    /creativecommons\.org\/publicdomain\/zero\//i.test(url);

  const publicDomain =
    /^(PUBLIC DOMAIN|PDM|PD(?:-|$))/.test(normalized) &&
    copyrighted === "false";

  const creativeCommons =
    /^CC BY(?:-SA)?(?:\s|$|-)/.test(normalized) &&
    /creativecommons\.org\/licenses\/by(?:-sa)?\//i.test(url);

  if (!cc0 && !publicDomain && !creativeCommons) {
    return null;
  }

  return {
    name: name || "Public domain",
    url: url || null,
  };
}

function emptyResult(reason: string): PhotoResult {
  return {
    image_url: null,
    source_url: null,
    source: null,
    title: null,
    credit: null,
    license: null,
    license_url: null,
    match_type: "none",
    matched_registration: null,
    confidence: "none",
    reason,
  };
}

async function searchCommons(search: string): Promise<WikiPage[]> {
  const params = new URLSearchParams({
    action: "query",
    format: "json",
    formatversion: "2",
    generator: "search",
    gsrsearch: `filetype:bitmap ${search}`,
    gsrnamespace: "6",
    gsrlimit: "30",
    prop: "imageinfo",
    iiprop: "url|mime|extmetadata",
    iiurlwidth: "1100",
    iiextmetadatafilter: "LicenseShortName|LicenseUrl|Copyrighted|Artist",
  });

  const response = await fetch(`${COMMONS_API}?${params}`, {
    headers: {
      "User-Agent":
        process.env.COMMONS_USER_AGENT ||
        "FlightDeck/0.1 (https://localhost:3000)",
      Accept: "application/json",
    },
    next: { revalidate: 86400 },
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    throw new Error(`Wikimedia Commons HTTP ${response.status}`);
  }

  const data = (await response.json()) as WikiResponse;

  // formatversion=2 returns an array, unlike version 1.
  const pages = data.query?.pages;

  if (Array.isArray(pages)) {
    return pages;
  }

  return Object.values(pages || {});
}

interface Candidate extends PhotoResult {
  score: number;
}

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const aircraft = (params.get("aircraft") || "").trim().toUpperCase();

  const airline = (params.get("airline") || "").trim();

  const registration = (params.get("registration") || "").trim().toUpperCase();

  const verifiedRegistration = /^[A-Z0-9-]{3,12}$/.test(registration)
    ? registration
    : null;

  const definition = AIRCRAFT[aircraft];

  if (!definition) {
    return NextResponse.json(emptyResult(`Unsupported aircraft: ${aircraft}`));
  }

  const searches: string[] = [];

  if (verifiedRegistration) {
    searches.push(verifiedRegistration);
  }

  if (airline) {
    searches.push(
      `${airline} ${definition.searches[0]}`,
      `${airline} ${aircraft}`,
    );
  } else {
    searches.push(definition.searches[0], `${aircraft} aircraft`);
  }

  const candidates: Candidate[] = [];
  let successfulSearches = 0;

  for (const query of [...new Set(searches)]) {
    let pages: WikiPage[];

    try {
      pages = await searchCommons(query);
      successfulSearches++;
    } catch (error) {
      console.warn(
        `[FlightPhoto] ${aircraft}: search failed (${query})`,
        error,
      );
      continue;
    }

    for (const page of pages) {
      const info = page.imageinfo?.[0];
      const title = page.title || "";

      if (
        !title ||
        !info?.thumburl ||
        !info.descriptionurl ||
        !["image/jpeg", "image/png", "image/webp"].includes(info.mime || "")
      ) {
        continue;
      }

      if (REJECTED_SUBJECTS.some((pattern) => pattern.test(title))) {
        continue;
      }

      const license = validLicense(info.extmetadata || {});

      if (!license) continue;

      // Match identity using the filename.
      // A loose description match is not enough.
      const typeMatch = matchesType(title, aircraft);

      if (!typeMatch) continue;

      const registrationMatch =
        !!verifiedRegistration &&
        matchesRegistration(title, verifiedRegistration);

      const airlineMatch = !!airline && matchesPhrase(title, airline);

      let matchType: MatchType;
      let score: number;

      if (registrationMatch) {
        // Reject visibly different airline identities.
        if (airline && !airlineMatch) {
          continue;
        }

        matchType = "registration";
        score = 120;
      } else if (airline) {
        // No random other airline when we know
        // the intended operator.
        if (!airlineMatch) continue;

        matchType = "airline_aircraft";
        score = 90;
      } else {
        matchType = "aircraft_type";
        score = 55;
      }

      if (/\b(landing|takeoff|taxi|departure)\b/i.test(title)) {
        score += 5;
      }

      candidates.push({
        image_url: info.thumburl,
        source_url: info.descriptionurl,
        source: "Wikimedia Commons",
        title,
        credit: stripHtml(info.extmetadata?.Artist?.value || "Unknown creator"),
        license: license.name,
        license_url: license.url,
        match_type: matchType,
        matched_registration: registrationMatch ? verifiedRegistration : null,
        confidence: registrationMatch ? "high" : "medium",
        score,
      });
    }
  }

  const unique = [
    ...new Map(
      candidates.map((candidate) => [candidate.source_url, candidate]),
    ).values(),
  ];

  unique.sort((a, b) => b.score - a.score);

  const best = unique[0];

  console.info(
    `[FlightPhoto] ${aircraft} / ${airline || "generic"}: ` +
      `${successfulSearches}/${searches.length} searches, ` +
      `${unique.length} matches`,
  );

  if (!best) {
    return NextResponse.json(
      emptyResult(
        successfulSearches === 0
          ? "Wikimedia Commons searches failed. Check server logs."
          : "No aircraft photograph matched the aircraft, airline and licence filters.",
      ),
    );
  }

  const { score: _score, ...result } = best;
  void _score;

  return NextResponse.json(result);
}
