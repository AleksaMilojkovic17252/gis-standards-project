import { latestValue } from "../api/sta";
import { tgsequenceUrl } from "../api/mf";
import { bracketIndex, distanceM, positionAt, speedKmhAt } from "../lib/geo";
import {
  useRailLines,
  useRailStations,
  useSnapshot,
  useTrainsOfDay,
} from "../state/queries";
import { resultText } from "../i18n";
import { formatUtc, formatUtcTime, useTime } from "../state/time";
import styles from "./Panel.module.css";

const dwellMaxDistanceM = 30;
const dwellMinSeconds = 30;

function formatValue(value: number | string | undefined, unit: string) {
  return value === undefined ? "-" : resultText(value, unit);
}

export default function TrainPanel({
  trainId,
  onClose,
}: {
  trainId?: string;
  onClose: () => void;
}) {
  const { time } = useTime();
  const { data: trains = [] } = useTrainsOfDay(time);
  const { data: lines = [] } = useRailLines();
  const { data: railStations = [] } = useRailStations();
  const { data: snapshot = [] } = useSnapshot(time);
  const train = trains.find((candidate) => candidate.id === trainId);
  if (!trainId) {
    return (
      <section className={styles.section}>
        <h2 className={styles.heading}>Voz</h2>
        <p className={styles.muted}>Kliknite na voz na mapi.</p>
      </section>
    );
  }
  if (!train) return null;

  const position = positionAt(train.times, train.coordinates, time);
  const speed = speedKmhAt(train.times, train.coordinates, time);
  const lineName =
    lines.find((line) => line.id === train.lineId)?.name ?? train.lineId;

  let nextStop: { name: string; time: number } | undefined;
  if (position) {
    for (
      let index = bracketIndex(train.times, time) + 1;
      index < train.times.length - 1;
      index++
    ) {
      const standing =
        distanceM(train.coordinates[index], train.coordinates[index + 1]) <
        dwellMaxDistanceM;
      const longEnough =
        (train.times[index + 1] - train.times[index]) / 1000 > dwellMinSeconds;
      if (standing && longEnough) {
        nextStop = { name: "", time: train.times[index] };
        const stopPosition = train.coordinates[index];
        nextStop.name = nearestName(railStations, stopPosition);
        break;
      }
    }
    if (!nextStop) {
      const last = train.coordinates[train.coordinates.length - 1];
      nextStop = {
        name: nearestName(railStations, last),
        time: train.times[train.times.length - 1],
      };
    }
  }

  const nearestWeather = position
    ? snapshot
        .map((station) => ({
          station,
          distance: distanceM(
            position,
            station.Locations[0].location.coordinates,
          ),
        }))
        .sort((a, b) => a.distance - b.distance)[0]
    : undefined;

  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>
        Voz {train.trainId}{" "}
        <button
          className={styles.select}
          onClick={onClose}
          aria-label="Zatvori panel voza"
        >
          ✕
        </button>
      </h2>
      <dl className={styles.facts}>
        <dt>Pruga</dt>
        <dd>{lineName}</dd>
        <dt>Vožnja</dt>
        <dd>
          {formatUtc(train.times[0])} →{" "}
          {formatUtcTime(train.times[train.times.length - 1])} UTC
        </dd>
        {position ? (
          <>
            <dt>Brzina</dt>
            <dd>{speed !== null ? `${Math.round(speed)} km/h` : "-"}</dd>
            <dt>Sledeća stanica</dt>
            <dd>
              {nextStop?.name}{" "}
              {nextStop && `(${formatUtcTime(nextStop.time)} UTC)`}
            </dd>
          </>
        ) : (
          <>
            <dt>Status</dt>
            <dd>ne vozi u ovo vreme</dd>
          </>
        )}
      </dl>
      {nearestWeather && (
        <>
          <p className={styles.muted}>
            Najbliža meteorološka stanica: {nearestWeather.station.name} (
            {resultText(nearestWeather.distance / 1000, "km")})
          </p>
          <dl className={styles.facts}>
            <dt>Temperatura vazduha</dt>
            <dd>
              {formatValue(
                latestValue(nearestWeather.station, "Air temperature")?.result,
                "°C",
              )}
            </dd>
            <dt>Padavine</dt>
            <dd>
              {formatValue(
                latestValue(nearestWeather.station, "Precipitation")?.result,
                "mm / 10 min",
              )}
            </dd>
            <dt>Vetar</dt>
            <dd>
              {formatValue(
                latestValue(nearestWeather.station, "Wind speed")?.result,
                "m/s",
              )}
            </dd>
            <dt>Stanje zemljišta</dt>
            <dd>
              {formatValue(
                latestValue(nearestWeather.station, "Soil state")?.result,
                "",
              )}{" "}
              (simulirano)
            </dd>
          </dl>
        </>
      )}
      <p>
        <a
          className={styles.link}
          href={tgsequenceUrl(train.id)}
          target="_blank"
          rel="noreferrer"
        >
          MF-JSON ove vožnje (OGC API - Moving Features)
        </a>
      </p>
    </section>
  );
}

function nearestName(
  stations: { name: string; lon: number; lat: number }[],
  [lon, lat]: [number, number],
): string {
  let best = "";
  let bestDistance = Infinity;
  for (const station of stations) {
    const distance = distanceM([lon, lat], [station.lon, station.lat]);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = station.name;
    }
  }
  return best;
}
