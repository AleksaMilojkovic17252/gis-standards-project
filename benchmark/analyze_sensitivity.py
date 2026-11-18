import csv
from pathlib import Path

results_folder = Path(__file__).resolve().parent / "results"
best_configs = {"postgis_points": "all", "mdb": "gist_trip", "postgis_lsm": "all"}
variants = ["baseline", "noise0", "noise10", "sampling5", "bunching", "chained"]
queries = [f"q{number}" for number in range(1, 8)]
storage_tolerance = 0.20


def folder_for(variant):
    return results_folder / ("trains_1x" if variant == "baseline" else f"sensitivity_{variant}")


def read_summary(variant):
    rows = csv.DictReader((folder_for(variant) / "summary.csv").open())
    return {(row["model"], row["query"]): row for row in rows if best_configs.get(row["model"]) == row["config"]}


def read_storage(variant):
    rows = csv.DictReader((folder_for(variant) / "indexes.csv").open())
    storage = {}
    for row in rows:
        if best_configs.get(row["model"]) == row["config"]:
            storage[row["model"]] = int(row["table_bytes"]) + int(row["index_bytes"])
    return storage


def ranking(summary, query):
    times = {model: float(summary[(model, query)]["median_ms"]) for model in best_configs}
    return sorted(times, key=times.get), times


def main():
    summaries = {variant: read_summary(variant) for variant in variants}
    storages = {variant: read_storage(variant) for variant in variants}
    baseline_ratio = {model: storages["baseline"][model] / storages["baseline"]["mdb"] for model in best_configs}

    output_rows = []
    all_rankings_stable = True
    all_storage_stable = True
    for variant in variants:
        print(f"\n== {variant}")
        ratio = {model: storages[variant][model] / storages[variant]["mdb"] for model in best_configs}
        storage_ok = all(abs(ratio[model] / baseline_ratio[model] - 1) <= storage_tolerance for model in best_configs)
        all_storage_stable &= storage_ok
        print("  storage (table + indexes): " + ", ".join(
            f"{model} {storages[variant][model] / 1e6:.1f} MB" for model in best_configs)
            + f"  ratio points:mdb:lsm = {ratio['postgis_points']:.2f} : 1 : {ratio['postgis_lsm']:.2f}"
            + ("" if storage_ok else "  <-- outside ±20 %"))
        for query in queries:
            order, times = ranking(summaries[variant], query)
            baseline_order, _ = ranking(summaries["baseline"], query)
            same_ranking = order == baseline_order
            all_rankings_stable &= same_ranking
            answers = {model: summaries[variant][(model, query)]["answer"] for model in best_configs}
            print(f"  {query}: " + " < ".join(f"{model} {times[model]:.1f}" for model in order)
                  + ("" if same_ranking else "   <-- ranking differs from baseline")
                  + f"   answers {answers}")
            output_rows.append([variant, query] + [round(times[model], 3) for model in best_configs]
                               + [" < ".join(order), same_ranking]
                               + [answers[model] for model in best_configs])
        output_rows.append([variant, "storage_mb"] + [round(storages[variant][model] / 1e6, 2) for model in best_configs]
                           + [f"{ratio['postgis_points']:.2f} : 1 : {ratio['postgis_lsm']:.2f}", storage_ok, "", "", ""])

    with (results_folder / "sensitivity_summary.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["variant", "query", "points_ms", "mdb_ms", "lsm_ms", "ranking", "same_as_baseline",
                         "points_answer", "mdb_answer", "lsm_answer"])
        writer.writerows(output_rows)

    print("\nSuccess criterion:")
    print(f"  same ranking for every query in every variant: {all_rankings_stable}")
    print(f"  storage ratios within ±{storage_tolerance:.0%} of baseline: {all_storage_stable}")
    print(f"Saved {results_folder / 'sensitivity_summary.csv'}")


if __name__ == "__main__":
    main()
