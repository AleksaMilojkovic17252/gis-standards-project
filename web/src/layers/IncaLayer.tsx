import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { ImageOverlay } from "react-leaflet";
import { fetchIncaCube } from "../api/ogc";
import { colorFor, type Scale } from "../lib/colors";
import { parseGrid, type Grid } from "../lib/coverage";
import { floorTo, useTime } from "../state/time";

export type IncaParameter = "T2M" | "RR";

function paint(grid: Grid, scale: Scale): string {
  const canvas = document.createElement("canvas");
  canvas.width = grid.width;
  canvas.height = grid.height;
  const context = canvas.getContext("2d");
  if (!context) return "";
  const image = context.createImageData(grid.width, grid.height);
  grid.values.forEach((value, index) => {
    if (value === null || Number.isNaN(value)) return;
    const [red, green, blue] = colorFor(scale, value);
    image.data.set(
      [red, green, blue, scale.min === 0 && value < 0.05 ? 0 : 255],
      index * 4,
    );
  });
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}

export default function IncaLayer({
  parameter,
  scale,
}: {
  parameter: IncaParameter;
  scale: Scale;
}) {
  const { time } = useTime();
  const hour = floorTo(time, 60);
  const { data } = useQuery({
    queryKey: ["inca", parameter, hour],
    queryFn: ({ signal }) => fetchIncaCube(parameter, hour, signal),
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === parameter ? previousData : undefined,
    staleTime: Infinity,
  });
  const overlay = useMemo(() => {
    const grid = data ? parseGrid(data, parameter) : null;
    if (!grid) return null;
    const halfX = (grid.east - grid.west) / Math.max(1, grid.width - 1) / 2;
    const halfY = (grid.north - grid.south) / Math.max(1, grid.height - 1) / 2;
    return {
      url: paint(grid, scale),
      bounds: [
        [grid.south - halfY, grid.west - halfX],
        [grid.north + halfY, grid.east + halfX],
      ] as [[number, number], [number, number]],
    };
  }, [data, parameter, scale]);
  if (!overlay) return null;
  return (
    <ImageOverlay url={overlay.url} bounds={overlay.bounds} opacity={0.6} />
  );
}
