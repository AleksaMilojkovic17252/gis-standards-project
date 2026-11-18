import { useQueries } from "@tanstack/react-query";
import { CircleMarker, Popup, Tooltip } from "react-leaflet";
import { fetchSeries, latestValue, type SnapshotStation } from "../api/sta";
import Sparkline from "../components/Sparkline";
import { propertyName, resultText } from "../i18n";
import { cssColorFor, SCALES, type ScaleKey } from "../lib/colors";
import { useSnapshot } from "../state/queries";
import { formatUtc, useTime } from "../state/time";
import styles from "./StationsLayer.module.css";

const propertyNames: Record<ScaleKey, string> = {
  air_temperature: "Air temperature",
  precipitation: "Precipitation",
  soil_moisture: "Soil moisture",
};

function formatResult(
  result: number | string | undefined,
  unit: string,
): string {
  return result === undefined ? "-" : resultText(result, unit);
}

function StationDetails({
  station,
  time,
}: {
  station: SnapshotStation;
  time: number;
}) {
  const from = time - 24 * 3600 * 1000;
  const series = useQueries({
    queries: station.Datastreams.map((datastream) => ({
      queryKey: ["series", datastream["@iot.id"], Math.floor(time / 600_000)],
      queryFn: () => fetchSeries(datastream["@iot.id"], from, time),
      staleTime: Infinity,
    })),
  });
  return (
    <div className={styles.popup}>
      <div className={styles.title}>{station.name}</div>
      <div className={styles.meta}>
        GeoSphere stanica {station.properties.geosphere_station_id},{" "}
        {station.properties.altitude_m} m · vrednosti u {formatUtc(time)} ·
        grafikoni: poslednja 24 h
      </div>
      <table className={styles.table}>
        <tbody>
          {station.Datastreams.map((datastream, index) => {
            const observations = series[index].data ?? [];
            const numeric = observations.filter(
              (observation) => typeof observation.result === "number",
            );
            return (
              <tr key={datastream["@iot.id"]}>
                <td>
                  {propertyName(datastream.ObservedProperty.name)}
                  {datastream.properties.simulated && (
                    <span className={styles.simulated}>simulirano</span>
                  )}
                </td>
                <td className={styles.value}>
                  {formatResult(
                    datastream.Observations[0]?.result,
                    datastream.unitOfMeasurement.symbol,
                  )}
                </td>
                <td>
                  {numeric.length > 1 && (
                    <Sparkline
                      times={numeric.map((observation) =>
                        Date.parse(observation.phenomenonTime),
                      )}
                      values={numeric.map(
                        (observation) => observation.result as number,
                      )}
                      width={90}
                      height={20}
                      unit={datastream.unitOfMeasurement.symbol}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function StationsLayer({
  colorBy,
  live,
}: {
  colorBy: ScaleKey;
  live?: { time: number };
}) {
  const { time: sliderTime } = useTime();
  const time = live?.time ?? sliderTime;
  const { data: stations = [] } = useSnapshot(time, live !== undefined);
  const scale = SCALES[colorBy];
  return (
    <>
      {stations.map((station) => {
        const [lon, lat] = station.Locations[0].location.coordinates;
        const value = latestValue(station, propertyNames[colorBy])?.result;
        const fill =
          typeof value === "number" ? cssColorFor(scale, value) : "#b9b8b2";
        return (
          <CircleMarker
            key={station["@iot.id"]}
            center={[lat, lon]}
            radius={8}
            pathOptions={{
              color: "#ffffff",
              weight: 2,
              fillColor: fill,
              fillOpacity: 1,
            }}
          >
            <Tooltip>
              {station.name}: {formatResult(value, scale.unit)}
            </Tooltip>
            <Popup maxWidth={380}>
              <StationDetails station={station} time={time} />
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}
