export interface AirportPhotoResult {
  airport_code: string;
  image_url: string | null;
  source_url?: string;
  title?: string;
  license?: string;
  credit?: string;
  source?: string;
  match_score?: number;
}

interface OpenverseImage {
  id: string;
  title: string | null;
  thumbnail: string | null;
  url: string | null;
  foreign_landing_url: string | null;
  creator: string | null;
  license: string;
  license_url: string | null;
  width: number | null;
  height: number | null;
}

interface OpenverseResponse {
  results: OpenverseImage[];
}

const BLACKLIST = [
  "airport diagram",
  "airport chart",
  "approach chart",
  "aeronautical chart",
  "airport map",
  "airport layout",
  "airport signage",
  "cargo container",
  "cargo pallet",
  "baggage cart",
  "boarding pass",
  "boarding ticket",
  "airport logo",
  "airline logo",
  "flight simulator",
  "scale model",
  "model aircraft",
  "terminal floor plan",
];

const AIRPORT_SUBJECTS = [
  "airport",
  "terminal",
  "runway",
  "apron",
  "taxiway",
  "control tower",
  "airfield",
  "aerial",
  "airside",
];

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function scoreAirportImage(
  title: string,
  icao: string,
  airportName: string,
): number {
  const normalized = normalize(title);
  const airportCode = icao.toLowerCase();

  if (BLACKLIST.some((term) => normalized.includes(term))) {
    return -1;
  }

  const excludedWords = [
    "diagram",
    "schematic",
    "illustration",
    "drawing",
    "blueprint",
  ];

  if (excludedWords.some((term) => normalized.includes(term))) {
    return -1;
  }

  const words = normalize(airportName)
    .split(" ")
    .filter(
      (word) =>
        word.length >= 4 && !["airport", "international", "the"].includes(word),
    );

  const codeMatch = normalized.split(" ").includes(airportCode);

  const nameMatches = words.filter((word) => normalized.includes(word));

  if (!codeMatch && nameMatches.length === 0) {
    return -1;
  }

  const subjectMatch = AIRPORT_SUBJECTS.some((term) =>
    normalized.includes(term),
  );

  if (!subjectMatch) {
    return -1;
  }

  let score = 30;

  if (codeMatch) score += 40;

  score += Math.min(nameMatches.length, 2) * 15;

  if (normalized.includes("terminal")) score += 20;
  if (normalized.includes("aerial")) score += 20;
  if (normalized.includes("runway")) score += 15;
  if (normalized.includes("apron")) score += 10;

  return score;
}

export async function searchOpenverseAirport(
  icao: string,
  airportName: string,
): Promise<AirportPhotoResult | null> {
  const searchQueries = [
    `${icao} airport`,
    `${airportName} terminal`,
    `${airportName} runway`,
  ];

  const candidates: AirportPhotoResult[] = [];

  for (const query of searchQueries) {
    const params = new URLSearchParams({
      q: query,
      license: "cc0,pdm",
      page_size: "20",
      mature: "false",
    });

    try {
      const response = await fetch(
        `https://api.openverse.org/v1/images/?${params}`,
        {
          headers: {
            Accept: "application/json",
          },
          next: {
            revalidate: 86400,
          },
          signal: AbortSignal.timeout(8000),
        },
      );

      if (!response.ok) continue;

      const data = (await response.json()) as OpenverseResponse;

      for (const image of data.results || []) {
        if (!image.title || !image.thumbnail || !image.foreign_landing_url) {
          continue;
        }

        const license = image.license.toLowerCase();

        if (!["cc0", "pdm"].includes(license)) {
          continue;
        }

        const score = scoreAirportImage(image.title, icao, airportName);

        if (score < 0) continue;

        // Prefer landscape images for flight cards.
        const landscape =
          image.width && image.height && image.width >= image.height;

        candidates.push({
          airport_code: icao,
          image_url: image.thumbnail,
          source_url: image.foreign_landing_url,
          title: image.title,
          license: image.license.toUpperCase(),
          credit: image.creator || "Unknown creator",
          source: "Openverse",
          match_score: score + (landscape ? 10 : 0),
        });
      }
    } catch {
      // Try the next search variation.
      continue;
    }
  }

  candidates.sort((a, b) => (b.match_score || 0) - (a.match_score || 0));

  return candidates[0] || null;
}
