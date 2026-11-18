import { Polygon } from "react-leaflet";
import { COLORS } from "../config";

export default function CorridorLayer({ ring }: { ring?: number[][] }) {
  if (!ring) return null;
  return (
    <Polygon
      positions={ring.map(([lon, lat]) => [lat, lon] as [number, number])}
      pathOptions={{
        color: COLORS.railHighlight,
        weight: 1.5,
        dashArray: "4 4",
        fillOpacity: 0.08,
      }}
    />
  );
}
