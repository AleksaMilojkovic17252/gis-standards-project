import { MF } from "../config";
import { getJson, mapWithLimit, withQuery } from "./http";

export type Train = {
  id: string;
  trainId: string;
  lineId: string;
  times: number[];
  coordinates: [number, number][];
};

type MovingFeature = {
  id: string;
  properties: { train_id: string; line_id: string };
};
type TemporalGeometrySequence = {
  geometrySequence: { datetimes: string[]; coordinates: [number, number][] }[];
};

const collection = "trains-simplified";

export async function fetchTrainsOfDay(dayStart: number): Promise<Train[]> {
  const dayEnd = dayStart + 24 * 3600 * 1000;
  const items = await getJson<{ features: MovingFeature[] }>(
    withQuery(`${MF}/collections/${collection}/items`, {
      datetime: `${new Date(dayStart).toISOString()}/${new Date(dayEnd).toISOString()}`,
      limit: "1000",
    }),
  );
  return mapWithLimit(items.features, 6, async (feature) => {
    const sequence = await getJson<TemporalGeometrySequence>(
      `${MF}/collections/${collection}/items/${feature.id}/tgsequence`,
    );
    const geometry = sequence.geometrySequence[0];
    return {
      id: feature.id,
      trainId: feature.properties.train_id,
      lineId: feature.properties.line_id,
      times: geometry
        ? geometry.datetimes.map((value) => Date.parse(value))
        : [],
      coordinates: geometry ? geometry.coordinates : [],
    };
  });
}

export function tgsequenceUrl(trainId: string): string {
  return `${MF}/collections/${collection}/items/${trainId}/tgsequence`;
}
