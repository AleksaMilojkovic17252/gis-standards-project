import { formatNumber } from "../i18n";
import styles from "./Sparkline.module.css";

type SparklineProps = {
  times: number[];
  values: (number | null)[];
  width?: number;
  height?: number;
  markerTime?: number;
  unit?: string;
};

export default function Sparkline({
  times,
  values,
  width = 120,
  height = 26,
  markerTime,
  unit = "",
}: SparklineProps) {
  const points = times
    .map((time, index) => [time, values[index]] as const)
    .filter(
      (point): point is readonly [number, number] =>
        typeof point[1] === "number",
    );
  if (points.length < 2)
    return <span className={styles.range}>nema podataka</span>;
  const minTime = points[0][0];
  const maxTime = points[points.length - 1][0];
  const minValue = Math.min(...points.map((point) => point[1]));
  const maxValue = Math.max(...points.map((point) => point[1]));
  const x = (time: number) =>
    ((time - minTime) / Math.max(1, maxTime - minTime)) * (width - 2) + 1;
  const y = (value: number) =>
    height -
    2 -
    ((value - minValue) / Math.max(1e-9, maxValue - minValue)) * (height - 4);
  const path = points
    .map(([time, value]) => `${x(time).toFixed(1)},${y(value).toFixed(1)}`)
    .join(" ");
  return (
    <span className={styles.wrapper}>
      <svg width={width} height={height} role="img">
        <polyline className={styles.line} points={path} />
        {markerTime !== undefined &&
          markerTime >= minTime &&
          markerTime <= maxTime && (
            <line
              className={styles.marker}
              x1={x(markerTime)}
              x2={x(markerTime)}
              y1={0}
              y2={height}
            />
          )}
      </svg>
      <span className={styles.range}>
        {formatNumber(minValue)} - {formatNumber(maxValue)} {unit}
      </span>
    </span>
  );
}
