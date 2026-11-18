import { distance } from "@turf/turf";

export function distanceM(
  from: [number, number],
  to: [number, number],
): number {
  return distance(from, to, { units: "meters" });
}

export function bracketIndex(times: number[], time: number): number {
  let low = 0;
  let high = times.length - 1;
  while (low < high - 1) {
    const middle = (low + high) >> 1;
    if (times[middle] <= time) low = middle;
    else high = middle;
  }
  return low;
}

export function positionAt(
  times: number[],
  coordinates: [number, number][],
  time: number,
): [number, number] | null {
  if (times.length === 0 || time < times[0] || time > times[times.length - 1])
    return null;
  const index = bracketIndex(times, time);
  const next = Math.min(index + 1, times.length - 1);
  const span = times[next] - times[index];
  const fraction = span > 0 ? (time - times[index]) / span : 0;
  const [lon1, lat1] = coordinates[index];
  const [lon2, lat2] = coordinates[next];
  return [lon1 + (lon2 - lon1) * fraction, lat1 + (lat2 - lat1) * fraction];
}

export function speedKmhAt(
  times: number[],
  coordinates: [number, number][],
  time: number,
): number | null {
  if (times.length < 2 || time < times[0] || time > times[times.length - 1])
    return null;
  const index = Math.min(bracketIndex(times, time), times.length - 2);
  const seconds = (times[index + 1] - times[index]) / 1000;
  return seconds > 0
    ? (distanceM(coordinates[index], coordinates[index + 1]) / seconds) * 3.6
    : 0;
}

export function polygonToWkt(ring: number[][], decimals = 4): string {
  return `POLYGON((${ring.map(([lon, lat]) => `${lon.toFixed(decimals)} ${lat.toFixed(decimals)}`).join(",")}))`;
}
