export type Scale = {
  label: string;
  unit: string;
  min: number;
  max: number;
  stops: string[];
};

export const SCALES = {
  air_temperature: {
    label: "Temperatura vazduha",
    unit: "°C",
    min: -5,
    max: 15,
    stops: ["#fdeee6", "#eb6834", "#7a2a0b"],
  },
  precipitation: {
    label: "Padavine",
    unit: "mm",
    min: 0,
    max: 3,
    stops: ["#e8f1fc", "#2a78d6", "#0d3b73"],
  },
  soil_moisture: {
    label: "Vlažnost zemljišta (simulirana)",
    unit: "%",
    min: 20,
    max: 42,
    stops: ["#e3f5ee", "#1baf7a", "#0a4d35"],
  },
} satisfies Record<string, Scale>;

export type ScaleKey = keyof typeof SCALES;

function hexToRgb(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

export function colorFor(
  scale: Scale,
  value: number,
): [number, number, number] {
  const position = Math.min(
    1,
    Math.max(0, (value - scale.min) / (scale.max - scale.min)),
  );
  const scaled = position * (scale.stops.length - 1);
  const index = Math.min(Math.floor(scaled), scale.stops.length - 2);
  const fraction = scaled - index;
  const start = hexToRgb(scale.stops[index]);
  const end = hexToRgb(scale.stops[index + 1]);
  return [0, 1, 2].map((channel) =>
    Math.round(start[channel] + (end[channel] - start[channel]) * fraction),
  ) as [number, number, number];
}

export function cssColorFor(scale: Scale, value: number): string {
  const [red, green, blue] = colorFor(scale, value);
  return `rgb(${red}, ${green}, ${blue})`;
}

export function gradientCss(scale: Scale): string {
  return `linear-gradient(to right, ${scale.stops.join(", ")})`;
}
