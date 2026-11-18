import { STA } from "../config";
import { getJson, withQuery } from "./http";

export type Observation = { phenomenonTime: string; result: number | string };

export type SnapshotDatastream = {
  "@iot.id": number;
  name: string;
  unitOfMeasurement: { symbol: string };
  properties: { simulated: boolean };
  ObservedProperty: { name: string };
  Observations: Observation[];
};

export type SnapshotStation = {
  "@iot.id": number;
  name: string;
  properties: {
    geosphere_station_id: number;
    altitude_m: number;
    line_id: string;
  };
  Locations: { location: { coordinates: [number, number] } }[];
  Datastreams: SnapshotDatastream[];
};

export async function fetchSnapshot(time: number): Promise<SnapshotStation[]> {
  const at = new Date(time).toISOString();
  const expand =
    "Locations($select=location)," +
    "Datastreams($select=id,name,unitOfMeasurement,properties;" +
    "$expand=ObservedProperty($select=name)," +
    `Observations($select=phenomenonTime,result;$filter=phenomenonTime le ${at};$orderby=phenomenonTime desc;$top=1))`;
  const url = withQuery(`${STA}/Things`, {
    $select: "id,name,properties",
    $expand: expand,
    $top: "100",
  });
  return (await getJson<{ value: SnapshotStation[] }>(url)).value;
}

export async function fetchSeries(
  datastreamId: number,
  from: number,
  to: number,
): Promise<Observation[]> {
  const url = withQuery(`${STA}/Datastreams(${datastreamId})/Observations`, {
    $filter: `phenomenonTime gt ${new Date(from).toISOString()} and phenomenonTime le ${new Date(to).toISOString()}`,
    $orderby: "phenomenonTime",
    $select: "phenomenonTime,result",
    $top: "500",
  });
  return (await getJson<{ value: Observation[] }>(url)).value;
}

export function latestValue(
  station: SnapshotStation,
  propertyName: string,
): Observation | undefined {
  return station.Datastreams.find(
    (datastream) => datastream.ObservedProperty.name === propertyName,
  )?.Observations[0];
}

export type StationLocation = {
  id: number;
  name: string;
  lon: number;
  lat: number;
};

export async function fetchStationLocations(): Promise<StationLocation[]> {
  const url = withQuery(`${STA}/Things`, {
    $select: "id,name",
    $expand: "Locations($select=location)",
    $top: "100",
  });
  const things = (await getJson<{ value: SnapshotStation[] }>(url)).value;
  return things.map((thing) => ({
    id: thing["@iot.id"],
    name: thing.name,
    lon: thing.Locations[0].location.coordinates[0],
    lat: thing.Locations[0].location.coordinates[1],
  }));
}
