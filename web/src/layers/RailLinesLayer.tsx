import { CircleMarker, Polyline, Tooltip } from "react-leaflet";
import { COLORS } from "../config";
import { useRailLines } from "../state/queries";

export default function RailLinesLayer({
  highlightedLineId,
}: {
  highlightedLineId?: string;
}) {
  const { data: lines = [] } = useRailLines();
  return (
    <>
      {lines.map((line) => {
        const positions = line.coordinates.map(
          ([lon, lat]) => [lat, lon] as [number, number],
        );
        const middle = positions[Math.floor(positions.length / 2)];
        const highlighted = line.id === highlightedLineId;
        return (
          <Polyline
            key={line.id}
            positions={positions}
            pathOptions={{
              color: highlighted ? COLORS.railHighlight : COLORS.rail,
              weight: highlighted ? 4 : 2.5,
            }}
          >
            <Tooltip sticky>{line.name}</Tooltip>
            <CircleMarker
              center={middle}
              radius={0}
              pathOptions={{ opacity: 0, fillOpacity: 0 }}
            >
              <Tooltip
                permanent
                direction="top"
                offset={[0, -4]}
                opacity={0.85}
              >
                {line.name.split(":")[0]}
              </Tooltip>
            </CircleMarker>
          </Polyline>
        );
      })}
    </>
  );
}
