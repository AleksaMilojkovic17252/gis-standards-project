import { INCA_BBOX, OGC } from "../config";
import { getJson, withQuery } from "./http";

export type RailLine = {
  id: string;
  name: string;
  lengthM: number;
  coordinates: [number, number][];
};
export type RailStation = { name: string; lon: number; lat: number };

type Feature<G, P> = { id: string | number; geometry: G; properties: P };
type FeatureCollection<G, P> = { features: Feature<G, P>[] };

export async function fetchRailLines(): Promise<RailLine[]> {
  const collection = await getJson<
    FeatureCollection<
      { coordinates: [number, number][] },
      { name: string; length_m: number }
    >
  >(
    withQuery(`${OGC}/collections/rail-lines/items`, {
      f: "json",
      limit: "10",
    }),
  );
  return collection.features.map((feature) => ({
    id: String(feature.id),
    name: feature.properties.name,
    lengthM: feature.properties.length_m,
    coordinates: feature.geometry.coordinates,
  }));
}

export async function fetchRailStations(): Promise<RailStation[]> {
  const collection = await getJson<
    FeatureCollection<{ coordinates: [number, number] }, { name: string }>
  >(
    withQuery(`${OGC}/collections/rail-stations/items`, {
      f: "json",
      limit: "2000",
    }),
  );
  return collection.features.map((feature) => ({
    name: feature.properties.name,
    lon: feature.geometry.coordinates[0],
    lat: feature.geometry.coordinates[1],
  }));
}

export async function fetchEdrParameterIds(): Promise<Record<string, string>> {
  const collection = await getJson<{
    parameter_names: Record<
      string,
      { observedProperty: { label: { en: string } } }
    >;
  }>(withQuery(`${OGC}/collections/stations-edr`, { f: "json" }));
  return Object.fromEntries(
    Object.entries(collection.parameter_names).map(([id, parameter]) => [
      parameter.observedProperty.label.en,
      id,
    ]),
  );
}

export async function fetchCorridorWeather(
  polygonWkt: string,
  from: number,
  to: number,
  parameterIds: string[],
) {
  return getJson<unknown>(
    withQuery(`${OGC}/collections/stations-edr/area`, {
      coords: polygonWkt,
      datetime: `${new Date(from).toISOString()}/${new Date(to).toISOString()}`,
      "parameter-name": parameterIds.join(","),
      f: "json",
    }),
  );
}

export async function fetchIncaCube(
  parameter: string,
  time: number,
  signal?: AbortSignal,
) {
  const at = new Date(time).toISOString();
  return getJson<unknown>(
    withQuery(`${OGC}/collections/inca-grid/cube`, {
      bbox: INCA_BBOX.join(","),
      datetime: at,
      "parameter-name": parameter,
      f: "json",
    }),
    signal,
  );
}
