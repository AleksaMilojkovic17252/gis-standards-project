import { PERIOD_END, PERIOD_START } from "../config";
import { formatUtc, useTime } from "../state/time";
import { IoMdPlay } from "react-icons/io";
import { IoMdPause } from "react-icons/io";
import styles from "./TimeSlider.module.css";

const speeds = [
  { label: "1 min/s", value: 60 },
  { label: "5 min/s", value: 300 },
  { label: "20 min/s", value: 1200 },
  { label: "1 sat/s", value: 3600 },
];

export default function TimeSlider() {
  const { time, setTime, playing, setPlaying, speed, setSpeed } = useTime();
  return (
    <div className={styles.bar}>
      <button
        className={styles.button}
        onClick={() => setPlaying(!playing)}
        aria-label={playing ? "Pauza" : "Pusti"}
      >
        {playing ? <IoMdPause /> : <IoMdPlay />}
      </button>
      <span className={styles.time}>{formatUtc(time)}</span>
      <input
        className={styles.slider}
        type="range"
        min={PERIOD_START}
        max={PERIOD_END}
        step={60_000}
        value={time}
        onChange={(event) => setTime(Number(event.target.value))}
        aria-label="Vreme"
      />
      <select
        className={styles.speed}
        value={speed}
        onChange={(event) => setSpeed(Number(event.target.value))}
        aria-label="Brzina reprodukcije"
      >
        {speeds.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
