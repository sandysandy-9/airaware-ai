export interface LocationSearchTarget {
  city?: string;
  latitude?: number;
  longitude?: number;
}

/**
 * Parse a user search query into either coordinates (`lat, lon` within valid Earth bounds)
 * or a clean city string so backend coordinate resolution works cleanly from the search bar.
 */
export function parseLocationSearchInput(rawQuery: string): LocationSearchTarget | null {
  const trimmed = rawQuery.trim();
  if (!trimmed) return null;

  const coordMatch = trimmed.match(
    /^([+-]?\d+(?:\.\d+)?)\s*[,;\s]\s*([+-]?\d+(?:\.\d+)?)$/
  );
  if (coordMatch) {
    const latitude = Number(coordMatch[1]);
    const longitude = Number(coordMatch[2]);
    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude) &&
      latitude >= -90 &&
      latitude <= 90 &&
      longitude >= -180 &&
      longitude <= 180
    ) {
      return { latitude, longitude };
    }
  }

  return { city: trimmed };
}
