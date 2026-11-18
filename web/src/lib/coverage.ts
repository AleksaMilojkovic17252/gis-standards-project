type Axis = {
  values?: (number | string)[];
  start?: number;
  stop?: number;
  num?: number;
};
type Range = {
  values: (number | null)[];
  shape?: number[];
  axisNames?: string[];
};
type Coverage = {
  domain: { domainType?: string; axes: Record<string, Axis> };
  ranges: Record<string, Range>;
};

export type Grid = {
  width: number;
  height: number;
  west: number;
  east: number;
  north: number;
  south: number;
  values: (number | null)[];
};
export type PointSeries = {
  lon: number;
  lat: number;
  parameter: string;
  times: number[];
  values: (number | null)[];
};

export function parseCoverageTime(value: string): number {
  return Date.parse(
    /[zZ]$|[+-]\d\d:?\d\d$/.test(value) ? value : `${value.slice(0, 19)}Z`,
  );
}

export function parseGrid(json: unknown, parameter: string): Grid | null {
  const coverage = json as Coverage;
  if (!coverage?.domain?.axes?.x || !coverage.ranges?.[parameter]) return null;
  const x = coverage.domain.axes.x;
  const y = coverage.domain.axes.y;
  return {
    width: x.num ?? 0,
    height: y.num ?? 0,
    west: Math.min(x.start ?? 0, x.stop ?? 0),
    east: Math.max(x.start ?? 0, x.stop ?? 0),
    north: Math.max(y.start ?? 0, y.stop ?? 0),
    south: Math.min(y.start ?? 0, y.stop ?? 0),
    values: coverage.ranges[parameter].values,
  };
}

export function parsePointSeriesCollection(json: unknown): PointSeries[] {
  const coverages = ((json as { coverages?: Coverage[] }).coverages ??
    []) as Coverage[];
  return coverages.flatMap((coverage) => {
    const axes = coverage.domain.axes;
    const lon = Number(axes.x.values?.[0]);
    const lat = Number(axes.y.values?.[0]);
    const times = (axes.t.values ?? []).map((value) =>
      parseCoverageTime(String(value)),
    );
    return Object.entries(coverage.ranges).map(([key, range]) => ({
      lon,
      lat,
      parameter: decodeURIComponent(key.replace(/\+/g, " ")),
      times,
      values: range.values,
    }));
  });
}
