import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import EndpointStatus from "./components/EndpointStatus";
import ErrorBoundary from "./components/ErrorBoundary";
import TimeSlider from "./components/TimeSlider";
import { ATTRIBUTION, LIVE_START } from "./config";
import CorridorLayer from "./layers/CorridorLayer";
import IncaLayer from "./layers/IncaLayer";
import RailLinesLayer from "./layers/RailLinesLayer";
import StationsLayer from "./layers/StationsLayer";
import TrainsLayer from "./layers/TrainsLayer";
import { SCALES } from "./lib/colors";
import CorridorPanel from "./panels/CorridorPanel";
import LayerPanel, { type LayerSettings } from "./panels/LayerPanel";
import TrainPanel from "./panels/TrainPanel";
import { useLiveFeed } from "./state/live";
import { TimeProvider } from "./state/time";
import styles from "./App.module.css";

const ENDPOINTS = [
  { name: "SensorThings (FROST)", url: "/sta/FROST-Server/v1.1" },
  { name: "OGC API (pygeoapi)", url: "/ogc/?f=json" },
  { name: "Moving Features", url: "/mf/" },
] as const;

export default function App() {
  const [layers, setLayers] = useState<LayerSettings>({
    rail: true,
    trains: true,
    stations: true,
    inca: false,
    live: false,
    stationColor: "air_temperature",
    incaParameter: "T2M",
  });
  const [selectedTrainId, setSelectedTrainId] = useState<string>();
  const [corridor, setCorridor] = useState<{
    lineId?: string;
    ring?: number[][];
  }>({});
  const liveStatus = useLiveFeed(layers.stations && layers.live);

  return (
    <TimeProvider>
      <div className={styles.app}>
        <aside className={styles.sidebar}>
          <h1 className={styles.title}>Vozovi i vreme u Austriji</h1>
          <p className={styles.subtitle}>
            SensorThings, EDR, Features i Moving Features u jednom klijentu. Bez
            sopstvenog servera: svaki sloj je zahtev ka OGC API-ju.
          </p>
          <LayerPanel
            settings={layers}
            onChange={setLayers}
            liveStatus={layers.live ? liveStatus : undefined}
          />
          <ErrorBoundary name="Panel voza">
            <TrainPanel
              trainId={selectedTrainId}
              onClose={() => setSelectedTrainId(undefined)}
            />
          </ErrorBoundary>
          <ErrorBoundary name="Panel koridora">
            <CorridorPanel
              onCorridor={(lineId, ring) => setCorridor({ lineId, ring })}
            />
          </ErrorBoundary>
          <h2 className={styles.sectionTitle}>Servisi</h2>
          <ul className={styles.statusList}>
            {ENDPOINTS.map((endpoint) => (
              <EndpointStatus
                key={endpoint.url}
                name={endpoint.name}
                url={endpoint.url}
              />
            ))}
          </ul>
          <p className={styles.footer}>
            Vreme: GeoSphere Austria (CC BY 4.0). Železnička mreža: ©
            OpenStreetMap saradnici (ODbL). Vožnje vozova, red vožnje, vlažnost
            i stanje zemljišta i deo temperatura zemljišta su simulirani.
          </p>
        </aside>
        <div className={styles.mapColumn}>
          <MapContainer
            className={styles.map}
            center={[47.6, 13.3]}
            zoom={7}
            preferCanvas
          >
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution={ATTRIBUTION}
              maxZoom={19}
            />
            {layers.inca && (
              <ErrorBoundary name="INCA sloj">
                <IncaLayer
                  parameter={layers.incaParameter}
                  scale={
                    layers.incaParameter === "T2M"
                      ? SCALES.air_temperature
                      : SCALES.precipitation
                  }
                />
              </ErrorBoundary>
            )}
            <CorridorLayer ring={corridor.ring} />
            {layers.rail && (
              <ErrorBoundary name="Sloj pruga">
                <RailLinesLayer highlightedLineId={corridor.lineId} />
              </ErrorBoundary>
            )}
            {layers.stations && (
              <ErrorBoundary name="Sloj stanica">
                <StationsLayer
                  colorBy={layers.stationColor}
                  live={
                    layers.live
                      ? { time: liveStatus.lastTime ?? LIVE_START }
                      : undefined
                  }
                />
              </ErrorBoundary>
            )}
            {layers.trains && (
              <ErrorBoundary name="Sloj vozova">
                <TrainsLayer
                  selectedTrainId={selectedTrainId}
                  onSelect={setSelectedTrainId}
                />
              </ErrorBoundary>
            )}
          </MapContainer>
          <TimeSlider />
        </div>
      </div>
    </TimeProvider>
  );
}
