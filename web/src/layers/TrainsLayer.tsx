import { CircleMarker, Tooltip } from "react-leaflet";
import { COLORS } from "../config";
import { positionAt, speedKmhAt } from "../lib/geo";
import { formatNumber } from "../i18n";
import { useTrainsOfDay } from "../state/queries";
import { useTime } from "../state/time";

type TrainsLayerProps = {
  selectedTrainId?: string;
  onSelect: (trainId: string) => void;
};

export default function TrainsLayer({
  selectedTrainId,
  onSelect,
}: TrainsLayerProps) {
  const { time } = useTime();
  const { data: trains = [] } = useTrainsOfDay(time);
  return (
    <>
      {trains.map((train) => {
        const position = positionAt(train.times, train.coordinates, time);
        if (!position) return null;
        const selected = train.id === selectedTrainId;
        const speed = speedKmhAt(train.times, train.coordinates, time);
        return (
          <CircleMarker
            key={train.id}
            center={[position[1], position[0]]}
            radius={selected ? 9 : 6}
            pathOptions={{
              color: "#ffffff",
              weight: 2,
              fillColor: selected ? COLORS.trainSelected : COLORS.train,
              fillOpacity: 1,
            }}
            eventHandlers={{ click: () => onSelect(train.id) }}
          >
            <Tooltip>
              Voz {train.trainId} ·{" "}
              {speed !== null ? `${formatNumber(speed, 0)} km/h` : ""}
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}
