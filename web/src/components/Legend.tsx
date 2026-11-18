import { formatNumber } from "../i18n";
import { gradientCss, type Scale } from "../lib/colors";
import styles from "./Legend.module.css";

export default function Legend({
  scale,
  title,
}: {
  scale: Scale;
  title?: string;
}) {
  return (
    <div className={styles.legend}>
      <div className={styles.title}>
        {title ?? `${scale.label} (${scale.unit})`}
      </div>
      <div className={styles.bar} style={{ background: gradientCss(scale) }} />
      <div className={styles.labels}>
        <span>
          ≤ {formatNumber(scale.min, 0)} {scale.unit}
        </span>
        <span>
          ≥ {formatNumber(scale.max, 0)} {scale.unit}
        </span>
      </div>
    </div>
  );
}
