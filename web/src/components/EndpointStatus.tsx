import { useQuery } from "@tanstack/react-query";
import styles from "./EndpointStatus.module.css";

type EndpointStatusProps = {
  name: string;
  url: string;
};

export default function EndpointStatus({ name, url }: EndpointStatusProps) {
  const { isPending, isError } = useQuery({
    queryKey: ["status", url],
    queryFn: async () => {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return true;
    },
    retry: false,
  });

  const state = isPending ? "checking" : isError ? "down" : "up";
  const stateLabels = { checking: "provera…", down: "ne radi", up: "radi" };

  return (
    <li className={styles.status}>
      <span className={`${styles.dot} ${styles[state]}`} />
      {name}: {stateLabels[state]}
    </li>
  );
}
