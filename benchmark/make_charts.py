import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

results_folder = Path(__file__).resolve().parent / "results"
figures_folder = Path("/figures")

models = ["postgis_points", "mdb", "postgis_lsm"]
model_colors = {"postgis_points": "#2a78d6", "mdb": "#eb6834", "postgis_lsm": "#1baf7a"}
best_configs = {"postgis_points": "all", "mdb": "gist_trip", "postgis_lsm": "all"}
queries = [f"q{number}" for number in range(1, 8)]
variants = ["baseline", "noise0", "noise10", "sampling5", "bunching", "chained"]
index_configs = ["none", "gist_geom", "brin_t", "btree_trip_t", "all"]

text = {
    "en": {
        "decimal": ".",
        "thousands": ",",
        "models": {"postgis_points": "PostGIS points", "mdb": "MobilityDB", "postgis_lsm": "PostGIS LineStringM"},
        "queries": {
            "q1": "Q1\nposition\nat t",
            "q2": "Q2\nbox +\nwindow",
            "q3": "Q3\nspeed,\nlength",
            "q4": "Q4\nclosest\napproach",
            "q5": "Q5\ntime near\nstations",
            "q6": "Q6\nstation\npassages",
            "q7": "Q7\nweather\nat train",
        },
        "variants": {"baseline": "baseline", "noise0": "noise0", "noise10": "noise10", "sampling5": "sampling5",
                     "bunching": "bunching", "chained": "chained"},
        "index_configs": ["no index", "GiST geom", "BRIN t", "B-tree (trip_id, t)", "all three"],
        "times_title": "Query run time per storage model (best index configuration, warm cache, median of 5)",
        "times_1x": "1× (1 day, 1.1 M points)",
        "times_10x": "10× (10 days, 11.2 M points)",
        "times_ylabel": "median run time (ms, log scale)",
        "storage_table": "table (incl. TOAST)",
        "storage_indexes": "indexes",
        "storage_xlabel": "MB at 10× (11.2 M points)",
        "storage_title": "Storage per model (best index configuration)",
        "heatmap_timeout": "timeout\n(>300 s)",
        "heatmap_colorbar": "median ms (log)",
        "heatmap_title": "PostGIS points at 10×: run time per index configuration",
        "scaling_ylabel": "run time 10× / 1× (log scale)",
        "scaling_same": "same time as at 1×",
        "scaling_linear": "10× data → 10× time",
        "scaling_title": "Scaling from 1× to 10×: selective queries stay flat, full scans grow linearly",
        "sql_ylabel": "lines of SQL",
        "sql_legend": "{model} ({total} lines in total)",
        "sql_title": "Query complexity: non-empty, non-comment lines of SQL",
        "sensitivity_ylabel": "median ms (log)",
        "sensitivity_title": "Sensitivity to generator realism (1×, best index configuration)",
    },
    "sr": {
        "decimal": ",",
        "thousands": ".",
        "models": {"postgis_points": "PostGIS tačke", "mdb": "MobilityDB", "postgis_lsm": "PostGIS LineStringM"},
        "queries": {
            "q1": "Q1\npoložaj\nu tren. t",
            "q2": "Q2\nokvir +\nperiod",
            "q3": "Q3\nbrzina,\ndužina",
            "q4": "Q4\nnajmanje\nrastojanje",
            "q5": "Q5\nvreme kod\nstanica",
            "q6": "Q6\nprolazak\nstanicom",
            "q7": "Q7\nmeteo\nkod voza",
        },
        "variants": {"baseline": "osnovni", "noise0": "bez šuma", "noise10": "šum 10 m", "sampling5": "uzorak 5 s",
                     "bunching": "grupisanje", "chained": "lančana kašnjenja"},
        "index_configs": ["bez indeksa", "GiST geom", "BRIN t", "B-stablo (trip_id, t)", "sva tri"],
        "times_title": "Vreme izvršavanja upita po modelu skladištenja "
                       "(najbolja konfiguracija indeksa, topli keš, medijana od 5)",
        "times_1x": "1× (1 dan, 1,1 M tačaka)",
        "times_10x": "10× (10 dana, 11,2 M tačaka)",
        "times_ylabel": "medijana vremena izvršavanja (ms, log. skala)",
        "storage_table": "tabela (uklj. TOAST)",
        "storage_indexes": "indeksi",
        "storage_xlabel": "MB pri 10× (11,2 M tačaka)",
        "storage_title": "Zauzeće prostora po modelu (najbolja konfiguracija indeksa)",
        "heatmap_timeout": "prekoračenje\n(>300 s)",
        "heatmap_colorbar": "medijana ms (log.)",
        "heatmap_title": "PostGIS tačke pri 10×: vreme izvršavanja po konfiguraciji indeksa",
        "scaling_ylabel": "vreme 10× / 1× (log. skala)",
        "scaling_same": "isto vreme kao pri 1×",
        "scaling_linear": "10× podataka → 10× vremena",
        "scaling_title": "Skaliranje od 1× do 10×: selektivni upiti ostaju isti, puna skeniranja rastu linearno",
        "sql_ylabel": "linije SQL-a",
        "sql_legend": "{model} (ukupno {total} linija)",
        "sql_title": "Složenost upita: neprazne linije SQL-a bez komentara",
        "sensitivity_ylabel": "medijana ms (log.)",
        "sensitivity_title": "Osetljivost na realističnost generatora (1×, najbolja konfiguracija indeksa)",
    },
}

text_primary = "#0b0b0b"
text_secondary = "#52514e"
grid_color = "#e4e3df"
surface = "#fcfcfb"
sequential = LinearSegmentedColormap.from_list("blue", ["#e8f1fc", "#2a78d6", "#0d3b73"])

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": text_secondary,
    "axes.labelcolor": text_primary,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": grid_color,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "xtick.color": text_secondary,
    "ytick.color": text_secondary,
    "legend.frameon": False,
    "figure.facecolor": surface,
    "axes.facecolor": surface,
    "savefig.facecolor": surface,
})


class Charts:
    def __init__(self, language):
        self.language = language
        self.t = text[language]
        self.output = figures_folder / language

    def number(self, value, digits):
        formatted = f"{value:,.{digits}f}"
        return formatted.replace(",", "\0").replace(".", self.t["decimal"]).replace("\0", self.t["thousands"])

    def format_ms(self, value):
        if value >= 1000:
            return f"{self.number(value / 1000, 1)} s"
        return self.number(value, 1) if value < 10 else self.number(value, 0)

    def plain_log_axis(self, axis):
        axis.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: self.number(value, 1 if value < 1 else 0)))
        axis.yaxis.set_minor_formatter(NullFormatter())

    def save(self, figure, name):
        self.output.mkdir(parents=True, exist_ok=True)
        for extension in ("png", "svg"):
            figure.savefig(self.output / f"{name}.{extension}", dpi=200, bbox_inches="tight")
        plt.close(figure)
        print(f"saved {self.language}/{name}.png / .svg")

    def grouped_bars(self, axis, values_by_model, ylabel, log_scale, value_format=None):
        width = 0.26
        for index, model in enumerate(models):
            positions = [query_index + (index - 1) * (width + 0.02) for query_index in range(len(queries))]
            values = values_by_model[model]
            axis.bar(positions, [value or 0 for value in values], width=width, color=model_colors[model],
                     label=self.t["models"][model], edgecolor=surface, linewidth=1)
            if value_format:
                for position, value in zip(positions, values):
                    if value:
                        axis.annotate(value_format(value), (position, value), xytext=(0, 2),
                                      textcoords="offset points", ha="center", va="bottom", fontsize=6.5,
                                      color=text_secondary, rotation=90)
        axis.set_xticks(range(len(queries)))
        axis.set_xticklabels([self.t["queries"][query] for query in queries], fontsize=7.5)
        axis.set_ylabel(ylabel)
        if log_scale:
            axis.set_yscale("log")
            self.plain_log_axis(axis)

    def query_times(self):
        figure, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
        for axis, label, title in zip(axes, ["trains_1x", "trains_10x"], [self.t["times_1x"], self.t["times_10x"]]):
            rows = summary(label)
            values = {model: [median_ms(rows, model, best_configs[model], query) for query in queries]
                      for model in models}
            self.grouped_bars(axis, values, self.t["times_ylabel"], True, self.format_ms)
            axis.set_title(title, loc="left")
            axis.set_ylim(0.5, 200_000)
        axes[0].legend(loc="upper left", ncols=3, fontsize=8)
        figure.suptitle(self.t["times_title"], x=0.01, ha="left", fontsize=11, fontweight="bold", color=text_primary)
        figure.tight_layout()
        self.save(figure, "fig_query_times")

    def storage(self):
        rows = read_csv(results_folder / "trains_10x" / "indexes.csv")
        sizes = {row["model"]: (int(row["table_bytes"]) / 1e6, int(row["index_bytes"]) / 1e6)
                 for row in rows if best_configs.get(row["model"]) == row["config"]}
        figure, axis = plt.subplots(figsize=(7, 2.6))
        labels = [self.t["models"][model] for model in models][::-1]
        tables = [sizes[model][0] for model in models][::-1]
        indexes = [sizes[model][1] for model in models][::-1]
        axis.barh(labels, tables, color="#52514e", height=0.5, label=self.t["storage_table"], edgecolor=surface,
                  linewidth=2)
        axis.barh(labels, indexes, left=tables, color="#b9b8b2", height=0.5, label=self.t["storage_indexes"],
                  edgecolor=surface, linewidth=2)
        for position, (table, index) in enumerate(zip(tables, indexes)):
            axis.annotate(f"{self.number(table + index, 0)} MB", (table + index, position), xytext=(4, 0),
                          textcoords="offset points", va="center", fontsize=8, color=text_primary)
        axis.set_xlabel(self.t["storage_xlabel"])
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: self.number(value, 0)))
        axis.grid(axis="x")
        axis.grid(axis="y", visible=False)
        axis.set_xlim(0, max(t + i for t, i in zip(tables, indexes)) * 1.18)
        axis.legend(loc="lower right", fontsize=8)
        axis.set_title(self.t["storage_title"], loc="left")
        figure.tight_layout()
        self.save(figure, "fig_storage")

    def points_index_heatmap(self):
        rows = summary("trains_10x")
        matrix = [[median_ms(rows, "postgis_points", config, query) for query in queries] for config in index_configs]
        present = [value for row in matrix for value in row if value]
        figure, axis = plt.subplots(figsize=(9, 3.4))
        display = [[value if value else float("nan") for value in row] for row in matrix]
        image = axis.imshow(display, cmap=sequential, norm=LogNorm(vmin=min(present), vmax=max(present)),
                            aspect="auto")
        low, high = math.log(min(present)), math.log(max(present))
        for row_index, row in enumerate(matrix):
            for column_index, value in enumerate(row):
                if value is None:
                    axis.text(column_index, row_index, self.t["heatmap_timeout"], ha="center", va="center",
                              fontsize=7, color=text_primary)
                    axis.add_patch(plt.Rectangle((column_index - 0.5, row_index - 0.5), 1, 1, fill=False,
                                                 hatch="////", edgecolor="#b9b8b2", linewidth=0))
                else:
                    darkness = (math.log(value) - low) / (high - low)
                    axis.text(column_index, row_index, self.format_ms(value), ha="center", va="center", fontsize=8,
                              color="white" if darkness > 0.55 else text_primary)
        axis.set_xticks(range(len(queries)))
        axis.set_xticklabels([self.t["queries"][query] for query in queries], fontsize=7.5)
        axis.set_yticks(range(len(index_configs)))
        axis.set_yticklabels(self.t["index_configs"])
        axis.grid(False)
        for spine in axis.spines.values():
            spine.set_visible(False)
        colorbar = figure.colorbar(image, ax=axis, fraction=0.03, pad=0.02)
        colorbar.set_label(self.t["heatmap_colorbar"])
        colorbar.ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: self.number(value, 0)))
        axis.set_title(self.t["heatmap_title"], loc="left")
        figure.tight_layout()
        self.save(figure, "fig_points_indexes")

    def scaling(self):
        one = summary("trains_1x")
        ten = summary("trains_10x")
        values = {model: [median_ms(ten, model, best_configs[model], query)
                          / median_ms(one, model, best_configs[model], query) for query in queries]
                  for model in models}
        figure, axis = plt.subplots(figsize=(9, 3.8))
        self.grouped_bars(axis, values, self.t["scaling_ylabel"], True, lambda value: f"{self.number(value, 1)}×")
        axis.axhline(1, color=text_secondary, linewidth=1, linestyle="--", label=self.t["scaling_same"])
        axis.axhline(10, color=text_secondary, linewidth=1, linestyle=":", label=self.t["scaling_linear"])
        axis.set_ylim(0.1, 60)
        axis.legend(loc="upper left", ncols=5, fontsize=7.5)
        axis.set_title(self.t["scaling_title"], loc="left")
        figure.tight_layout()
        self.save(figure, "fig_scaling")

    def sql_lines(self):
        rows = read_csv(results_folder / "sql_complexity.csv")
        lines = {(row["model"], row["query"]): int(row["lines"]) for row in rows}
        values = {model: [lines[(model, query)] for query in queries] for model in models}
        figure, axis = plt.subplots(figsize=(9, 3.4))
        self.grouped_bars(axis, values, self.t["sql_ylabel"], False, lambda value: f"{value:.0f}")
        axis.legend([self.t["sql_legend"].format(model=self.t["models"][model], total=sum(values[model]))
                     for model in models], loc="upper left", ncols=3, fontsize=8)
        axis.set_ylim(0, 34)
        axis.set_title(self.t["sql_title"], loc="left")
        figure.tight_layout()
        self.save(figure, "fig_sql_lines")

    def sensitivity(self):
        data = {}
        for variant in variants:
            rows = summary("trains_1x" if variant == "baseline" else f"sensitivity_{variant}")
            for model in models:
                for query in queries:
                    data[(variant, model, query)] = median_ms(rows, model, best_configs[model], query)
        figure, axes = plt.subplots(1, 7, figsize=(13, 3.6))
        markers = {"postgis_points": "o", "mdb": "s", "postgis_lsm": "^"}
        for axis, query in zip(axes, queries):
            for model in models:
                axis.scatter(range(len(variants)), [data[(variant, model, query)] for variant in variants],
                             color=model_colors[model], marker=markers[model], s=28, edgecolor=surface,
                             linewidth=0.8, label=self.t["models"][model], zorder=3)
            axis.set_yscale("log")
            self.plain_log_axis(axis)
            axis.set_xticks(range(len(variants)))
            axis.set_xticklabels([self.t["variants"][variant] for variant in variants], rotation=90, fontsize=7)
            axis.set_title(self.t["queries"][query].replace("\n", " "), fontsize=7, loc="left")
            axis.grid(axis="both")
        axes[0].set_ylabel(self.t["sensitivity_ylabel"])
        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc="upper right", ncols=3, fontsize=8)
        figure.suptitle(self.t["sensitivity_title"], x=0.01, ha="left", fontsize=11, fontweight="bold",
                        color=text_primary)
        figure.tight_layout(rect=(0, 0, 1, 0.93))
        self.save(figure, "fig_sensitivity")

    def all(self):
        self.query_times()
        self.storage()
        self.points_index_heatmap()
        self.scaling()
        self.sql_lines()
        self.sensitivity()


def read_csv(path):
    return list(csv.DictReader(path.open()))


def summary(label):
    return {(row["model"], row["config"], row["query"]): row
            for row in read_csv(results_folder / label / "summary.csv")}


def median_ms(rows, model, config, query):
    value = rows[(model, config, query)]["median_ms"]
    return float(value) if value else None


def main():
    for language in ("sr", "en"):
        Charts(language).all()


if __name__ == "__main__":
    main()
