import type { Feature, FeatureCollection, Polygon } from "geojson";
import raw from "../../../data/geo/districts.geojson?raw";

export interface DistrictProperties {
  district_id: string;
}

export type DistrictCollection = FeatureCollection<Polygon, DistrictProperties>;

export const districts = JSON.parse(raw) as DistrictCollection;

export function polygonCentroid(feature: Feature<Polygon, DistrictProperties>): [number, number] {
  const ring = feature.geometry.coordinates[0] ?? [];
  const points = ring.length > 1 ? ring.slice(0, -1) : ring;
  if (points.length === 0) return [0, 0];
  let longitude = 0;
  let latitude = 0;
  for (const pair of points) {
    longitude += pair[0] ?? 0;
    latitude += pair[1] ?? 0;
  }
  return [latitude / points.length, longitude / points.length];
}

export function districtFromAttributes(attributes: string[]): string | null {
  const match = attributes.find((item) => item.startsWith("district:"));
  return match ? match.slice("district:".length) : null;
}
