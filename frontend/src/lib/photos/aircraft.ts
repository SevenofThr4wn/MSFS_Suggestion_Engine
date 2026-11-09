export const AIRCRAFT_SEARCH_TERMS: Record<string, string[]> = {
  A388: ["A380-800", "A380"],
  A359: ["A350-900"],
  A35K: ["A350-1000"],
  A333: ["A330-300"],
  A343: ["A340-300"],
  A346: ["A340-600"],
  B77W: ["777-300ER"],
  B77L: ["777-200LR"],
  B772: ["777-200ER", "777-200"],
  B738: ["737-800"],
  B38M: ["737 MAX 8", "737-8 MAX"],
  A319: ["A319"],
  A320: ["A320"],
  A321: ["A321"],
};

export function normalizeText(value: string): string {
  return value
    .normalize("NFKD")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, " ")
    .trim();
}

export function compactText(value: string): string {
  return normalizeText(value).replace(/\s+/g, "");
}

export function normalizeRegistration(
  value: string | null | undefined,
): string | null {
  if (!value) return null;

  const normalized = value.trim().toUpperCase().replace(/\s+/g, "");

  if (!/^[A-Z0-9-]{3,12}$/.test(normalized)) {
    return null;
  }

  return normalized;
}

export function matchesRegistration(
  text: string,
  registration: string,
): boolean {
  // Prevent a partial registration from matching
  // another registration with additional characters.
  const normalizedText = normalizeText(text);
  const normalizedRegistration = normalizeText(registration);

  const paddedText = ` ${normalizedText} `;
  const paddedRegistration = ` ${normalizedRegistration} `;

  if (paddedText.includes(paddedRegistration)) {
    return true;
  }

  // Some image filenames omit the hyphen in
  // aircraft registrations.
  const compactRegistration = compactText(registration);

  const tokens = normalizedText.split(" ");

  return tokens.some((token) => token === compactRegistration);
}

export function matchesAirline(text: string, airline: string): boolean {
  const normalizedText = normalizeText(text);
  const normalizedAirline = normalizeText(airline);

  if (!normalizedAirline) return false;

  return ` ${normalizedText} `.includes(` ${normalizedAirline} `);
}

export function matchesAircraftType(
  text: string,
  aircraftCode: string,
): boolean {
  const terms = AIRCRAFT_SEARCH_TERMS[aircraftCode];

  if (!terms) return false;

  const normalizedText = compactText(text);

  return terms.some((term) => normalizedText.includes(compactText(term)));
}

export function isExcludedPhoto(title: string): boolean {
  const text = normalizeText(title);

  const excluded = [
    "DIAGRAM",
    "SCHEMATIC",
    "DRAWING",
    "ILLUSTRATION",
    "MODEL AIRCRAFT",
    "FLIGHT SIMULATOR",
    "COCKPIT INTERIOR",
    "SEAT MAP",
    "AIRPORT CHART",
    "CARGO CONTAINER",
    "BAGGAGE CART",
  ];

  return excluded.some((term) => text.includes(term));
}
