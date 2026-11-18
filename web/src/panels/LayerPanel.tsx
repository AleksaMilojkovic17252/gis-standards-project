import Legend from "../components/Legend";
import { SCALES, type ScaleKey } from "../lib/colors";
import type { IncaParameter } from "../layers/IncaLayer";
import type { LiveStatus } from "../state/live";
import { formatUtc } from "../state/time";
import styles from "./Panel.module.css";

export type LayerSettings = {
  rail: boolean;
  trains: boolean;
  stations: boolean;
  inca: boolean;
  live: boolean;
  stationColor: ScaleKey;
  incaParameter: IncaParameter;
};

type LayerPanelProps = {
  settings: LayerSettings;
  onChange: (settings: LayerSettings) => void;
  liveStatus?: LiveStatus;
};

export default function LayerPanel({
  settings,
  onChange,
  liveStatus,
}: LayerPanelProps) {
  const toggle = (key: "rail" | "trains" | "stations" | "inca" | "live") =>
    onChange({ ...settings, [key]: !settings[key] });
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Slojevi</h2>
      <label className={styles.row}>
        <input
          type="checkbox"
          checked={settings.rail}
          onChange={() => toggle("rail")}
        />{" "}
        Pruge (OGC API - Features)
      </label>
      <label className={styles.row}>
        <input
          type="checkbox"
          checked={settings.trains}
          onChange={() => toggle("trains")}
        />{" "}
        Vozovi (Moving Features, simulirani)
      </label>
      <label className={styles.row}>
        <input
          type="checkbox"
          checked={settings.stations}
          onChange={() => toggle("stations")}
        />{" "}
        Meteorološke stanice (SensorThings)
      </label>
      {settings.stations && (
        <div className={styles.row}>
          <span className={styles.muted}>boja prema</span>
          <select
            className={styles.select}
            value={settings.stationColor}
            onChange={(event) =>
              onChange({
                ...settings,
                stationColor: event.target.value as ScaleKey,
              })
            }
          >
            {Object.entries(SCALES).map(([key, scale]) => (
              <option key={key} value={key}>
                {scale.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {settings.stations && (
        <label className={styles.row}>
          <input
            type="checkbox"
            checked={settings.live}
            onChange={() => toggle("live")}
          />{" "}
          Uživo (SensorThings MQTT, reprodukcija)
        </label>
      )}
      {settings.stations && liveStatus && (
        <p className={styles.muted}>
          {liveStatus.connected ? "povezano" : "povezivanje…"} · poruka:{" "}
          {liveStatus.messages}
          {liveStatus.lastTime !== undefined &&
            ` · poslednja ${formatUtc(liveStatus.lastTime)}`}
        </p>
      )}
      {settings.stations && (
        <Legend
          scale={SCALES[settings.stationColor]}
          title={`Stanice: ${SCALES[settings.stationColor].label}`}
        />
      )}
      <label className={styles.row}>
        <input
          type="checkbox"
          checked={settings.inca}
          onChange={() => toggle("inca")}
        />{" "}
        INCA mreža (EDR cube, po satu)
      </label>
      {settings.inca && (
        <>
          <div className={styles.row}>
            <select
              className={styles.select}
              value={settings.incaParameter}
              onChange={(event) =>
                onChange({
                  ...settings,
                  incaParameter: event.target.value as IncaParameter,
                })
              }
            >
              <option value="T2M">Temperatura vazduha</option>
              <option value="RR">Padavine (po satu)</option>
            </select>
          </div>
          <Legend
            scale={
              settings.incaParameter === "T2M"
                ? SCALES.air_temperature
                : SCALES.precipitation
            }
            title={
              settings.incaParameter === "T2M"
                ? "INCA temperatura vazduha (°C)"
                : "INCA padavine (mm/h)"
            }
          />
          <p className={styles.muted}>
            Oko 5 MB CoverageJSON-a po satu; najbolje koristiti dok je
            pauzirano.
          </p>
        </>
      )}
    </section>
  );
}
