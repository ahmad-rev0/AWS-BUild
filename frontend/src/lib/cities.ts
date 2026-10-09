import type { CatalogCity } from "../types/catalog";

/** City centers for map placement. World Bank project rows do not include coordinates. */
export const CITY_CENTERS: Record<string, [number, number]> = {
  Karachi: [24.8607, 67.0011],
  Lahore: [31.5204, 74.3587],
  Dhaka: [23.8103, 90.4125],
  Chittagong: [22.3569, 91.7832],
  Chattogram: [22.3569, 91.7832],
};

export interface MapCity {
  key: string;
  label: string;
  country: string;
  count: number;
  center: [number, number];
  names: string[];
}

export function mapCities(cities: CatalogCity[]): MapCity[] {
  const groups = new Map<string, MapCity>();
  for (const city of cities) {
    const key = city.city === "Chattogram" ? "Chittagong" : city.city;
    const center = CITY_CENTERS[key];
    if (!center) continue;
    const groupKey = `${city.country}|${key}`;
    const existing = groups.get(groupKey);
    if (existing) {
      existing.count += city.project_count;
      existing.names.push(city.city);
      existing.label = existing.names.join(" / ");
    } else {
      groups.set(groupKey, {
        key,
        label: city.city,
        country: city.country,
        count: city.project_count,
        center,
        names: [city.city],
      });
    }
  }
  return [...groups.values()];
}

export function cityCenter(city: string): [number, number] | null {
  return CITY_CENTERS[city === "Chattogram" ? "Chittagong" : city] ?? null;
}
