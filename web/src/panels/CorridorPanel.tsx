import { buffer, lineString, simplify } from "@turf/turf";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchCorridorWeather } from "../api/ogc";
import Sparkline from "../components/Sparkline";
import { CORRIDOR_WIDTH_KM, MAX_CORRIDOR_VERTICES } from "../config";
import { parsePointSeriesCollection, type PointSeries } from "../lib/coverage";
import { distanceM, polygonToWkt } from "../lib/geo";
import {
  useEdrParameterIds,
  useRailLines,
  useStationLocations,
} from "../state/queries";
import { formatNumber } from "../i18n";
import { floorTo, formatUtcDate, useTime } from "../state/time";
import styles from "./Panel.module.css";

type CorridorPanelProps = {
  onCorridor: (lineId?: string, ring?: number[][]) => void;
};
type StationRow = { name: string; rain?: number; temperature?: PointSeries };

const dayMs = 24 * 3600 * 1000;

function corridorRing(coordinates: [number, number][]): number[][] {
  const line = simplify(lineString(coordinates), { tolerance: 0.001 });
  const polygon = buffer(line, CORRIDOR_WIDTH_KM, {
    units: "kilometers",
    steps: 4,
  });
  if (!polygon || polygon.geometry.type !== "Polygon")
    throw new Error("Buffer did not produce a polygon");
  let tolerance = 0.002;
  let ring = polygon.geometry.coordinates[0];
  while (ring.length > MAX_CORRIDOR_VERTICES && tolerance < 0.5) {
    const simplified = simplify(polygon, { tolerance });
    ring =
      simplified.geometry.type === "Polygon"
        ? simplified.geometry.coordinates[0]
        : ring;
    tolerance *= 1.5;
  }
  return ring;
}

function formatDay(dayStart: number): string {
  return formatUtcDate(dayStart);
}

export default function CorridorPanel({ onCorridor }: CorridorPanelProps) {
  const { time } = useTime();
  const { data: lines = [] } = useRailLines();
  const { data: parameterIds } = useEdrParameterIds();
  const { data: stations = [] } = useStationLocations();
  const [selectedLineId, setSelectedLineId] = useState("westbahn");
  const [activeLineId, setActiveLineId] = useState<string>();
  const dayStart = floorTo(time, 24 * 60);

  const activeLine = lines.find((line) => line.id === activeLineId);
  const ring = useMemo(
    () => (activeLine ? corridorRing(activeLine.coordinates) : undefined),
    [activeLine],
  );
  const wkt = useMemo(() => (ring ? polygonToWkt(ring) : undefined), [ring]);

  const onCorridorRef = useRef(onCorridor);
  onCorridorRef.current = onCorridor;
  useEffect(() => {
    onCorridorRef.current(activeLineId, ring);
  }, [activeLineId, ring]);

  const corridor = useQuery({
    queryKey: ["corridor", activeLineId, dayStart],
    enabled: Boolean(wkt && parameterIds),
    queryFn: async () => {
      const ids = [
        parameterIds!["Precipitation"],
        parameterIds!["Air temperature"],
      ];
      const json = await fetchCorridorWeather(
        wkt!,
        dayStart,
        dayStart + dayMs - 1,
        ids,
      );
      return { dayStart, series: parsePointSeriesCollection(json) };
    },
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === activeLineId ? previousData : undefined,
    staleTime: Infinity,
  });

  const rows = useMemo(() => {
    if (!corridor.data) return [];
    const byStation: Record<string, StationRow> = {};
    for (const series of corridor.data.series) {
      const key = `${series.lon.toFixed(4)},${series.lat.toFixed(4)}`;
      const nearest = stations
        .map((station) => ({
          station,
          distance: distanceM(
            [series.lon, series.lat],
            [station.lon, station.lat],
          ),
        }))
        .sort((a, b) => a.distance - b.distance)[0];
      const row = (byStation[key] ??= { name: nearest?.station.name ?? key });
      if (series.parameter.startsWith("Precipitation")) {
        row.rain = series.values.reduce<number>(
          (sum, value) => sum + (value ?? 0),
          0,
        );
      } else {
        row.temperature = series;
      }
    }
    return Object.values(byStation).sort(
      (a, b) => (b.rain ?? 0) - (a.rain ?? 0),
    );
  }, [corridor.data, stations]);

  const shownDay = corridor.data?.dayStart;
  const loadingNewDay =
    corridor.isFetching && shownDay !== undefined && shownDay !== dayStart;

  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Vreme duž pruge (EDR area)</h2>
      <div className={styles.row}>
        <select
          className={styles.select}
          value={selectedLineId}
          onChange={(event) => {
            setSelectedLineId(event.target.value);
            if (activeLineId) setActiveLineId(event.target.value);
          }}
        >
          {lines.map((line) => (
            <option key={line.id} value={line.id}>
              {line.name}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.row}>
        {activeLineId ? (
          <button
            className={styles.select}
            onClick={() => setActiveLineId(undefined)}
          >
            Ukloni koridor
          </button>
        ) : (
          <button
            className={styles.button}
            onClick={() => setActiveLineId(selectedLineId)}
            disabled={!lines.length}
          >
            Prikaži stanice u pojasu od {CORRIDOR_WIDTH_KM} km
          </button>
        )}
        {activeLineId && corridor.isPending && (
          <span className={styles.muted}>Upit u toku…</span>
        )}
      </div>
      {corridor.error && (
        <p className={styles.error}>{String(corridor.error)}</p>
      )}
      {activeLineId && corridor.data && ring && wkt && (
        <>
          <p className={styles.muted}>
            Dan {formatDay(corridor.data.dayStart)} (prati klizač vremena)
            {loadingNewDay && ` · učitava se ${formatDay(dayStart)}`}. Pojas
            pojednostavljen na {ring.length} temena ({wkt.length} znakova WKT-a
            u URL-u). Pronađeno stanica: {rows.length}.
          </p>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Stanica</th>
                <th className={styles.number}>Kiša (dan)</th>
                <th>Temperatura</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className={styles.number}>
                    {row.rain !== undefined
                      ? `${formatNumber(row.rain)} mm`
                      : "-"}
                  </td>
                  <td>
                    {row.temperature && (
                      <Sparkline
                        times={row.temperature.times}
                        values={row.temperature.values}
                        width={80}
                        height={20}
                        markerTime={time}
                        unit="°C"
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
