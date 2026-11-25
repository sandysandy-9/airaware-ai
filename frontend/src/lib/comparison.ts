import type { CityInfo } from "./types";

export interface ComparisonCityOption {
  id: string;
  name: string;
  state?: string | null;
}

export const MIN_COMPARISON_CITIES = 2;
export const MAX_COMPARISON_CITIES = 6;

/**
 * Resolve available cities for comparison from fetchCities(), falling back gracefully
 * to fallbackCities without inventing unsupported coordinates or entries.
 */
export function resolveComparisonCityOptions(
  apiCities: CityInfo[] | null | undefined,
  fallbackCities: ComparisonCityOption[]
): ComparisonCityOption[] {
  const source: ComparisonCityOption[] =
    Array.isArray(apiCities) && apiCities.length > 0 ? apiCities : fallbackCities;

  const seenIds = new Set<string>();
  const deduped: ComparisonCityOption[] = [];
  for (const c of source) {
    const id = (c.id || "").trim();
    const name = (c.name || "").trim();
    if (!id || !name || seenIds.has(id)) continue;
    seenIds.add(id);
    deduped.push({ id, name, state: c.state });
  }
  return deduped;
}

/**
 * Immutable, functional-state-safe city selection toggle preventing duplicates and enforcing [min, max].
 */
export function toggleComparisonCitySelection(
  prevSelected: string[],
  cityId: string,
  minCities: number = MIN_COMPARISON_CITIES,
  maxCities: number = MAX_COMPARISON_CITIES
): string[] {
  const uniquePrev: string[] = [];
  for (const id of prevSelected) {
    if (!uniquePrev.includes(id)) uniquePrev.push(id);
  }

  if (uniquePrev.includes(cityId)) {
    if (uniquePrev.length <= minCities) {
      return uniquePrev;
    }
    return uniquePrev.filter((id) => id !== cityId);
  }

  if (uniquePrev.length >= maxCities) {
    return uniquePrev;
  }
  return [...uniquePrev, cityId];
}

export function buildComparisonRequestPayload(
  selectedIds: string[],
  availableCities: ComparisonCityOption[]
): Array<{ city: string }> {
  const uniqueIds = Array.from(new Set(selectedIds));
  return uniqueIds.map((cid) => {
    const match = availableCities.find((c) => c.id === cid);
    return { city: match ? match.name : cid };
  });
}
