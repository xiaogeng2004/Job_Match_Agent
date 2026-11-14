from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = PROJECT_ROOT / "reports" / "figures"
BACKGROUND = "#F7F6F2"
INK = "#000000"
MUTED = "#000000"
GRID = "#D8D8D2"
ACCENT = "#62766D"
SERIES = ("#8C9290", "#A19888", "#62766D")


def style_axes(axis):
    axis.set_facecolor(BACKGROUND)
    axis.tick_params(colors=MUTED, labelsize=9)
    for spine in axis.spines.values():
        spine.set_color(GRID)
        spine.set_linewidth(0.8)
    axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.65)
    axis.set_axisbelow(True)


def draw_workflow(path: Path):
    fig, axis = plt.subplots(figsize=(10.6, 4.6), dpi=180)
    fig.patch.set_facecolor(BACKGROUND)
    axis.set_facecolor(BACKGROUND)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    boxes = [
        (0.03, 0.57, 0.18, 0.20, "Resume input\nPDF / DOCX / TXT"),
        (0.28, 0.57, 0.18, 0.20, "Parse + privacy\nin-memory only"),
        (0.53, 0.57, 0.18, 0.20, "Skill extraction\nwith evidence"),
        (0.78, 0.57, 0.18, 0.20, "Filter candidates\ncity / type / time"),
        (0.78, 0.20, 0.18, 0.20, "Role classifier\nchar TF-IDF + LR"),
        (0.53, 0.20, 0.18, 0.20, "Explainable score\ncoverage + similarity"),
        (0.28, 0.20, 0.18, 0.20, "Results + gaps\nsource evidence"),
        (0.03, 0.20, 0.18, 0.20, "Human correction\nand feedback"),
    ]
    for x, y, width, height, label in boxes:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.012",
            linewidth=0.9,
            edgecolor="#AEB2AC",
            facecolor="#ECEBE6",
        )
        axis.add_patch(patch)
        axis.text(
            x + width / 2,
            y + height / 2,
            label,
            ha="center",
            va="center",
            color=INK,
            fontsize=9.2,
            family="DejaVu Sans",
            linespacing=1.45,
        )

    arrows = [
        ((0.21, 0.67), (0.28, 0.67)),
        ((0.46, 0.67), (0.53, 0.67)),
        ((0.71, 0.67), (0.78, 0.67)),
        ((0.87, 0.57), (0.87, 0.40)),
        ((0.78, 0.30), (0.71, 0.30)),
        ((0.53, 0.30), (0.46, 0.30)),
        ((0.28, 0.30), (0.21, 0.30)),
        ((0.12, 0.40), (0.12, 0.57)),
    ]
    for start, end in arrows:
        axis.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=10,
                linewidth=1.1,
                color=ACCENT,
                shrinkA=0,
                shrinkB=0,
            )
        )

    axis.text(
        0.5,
        0.94,
        "Controlled Agent workflow",
        ha="center",
        va="center",
        fontsize=13,
        color=INK,
        family="DejaVu Sans",
    )
    axis.text(
        0.5,
        0.055,
        "Feedback is persisted without resume text; low-confidence results require user confirmation.",
        ha="center",
        va="center",
        fontsize=8.5,
        color=MUTED,
        family="DejaVu Sans",
    )
    fig.tight_layout(pad=0.4)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def draw_confusion_matrix(path: Path):
    metrics = json.loads(
        (PROJECT_ROOT / "models" / "metrics.json").read_text(encoding="utf-8")
    )
    labels = [
        "ALG",
        "BE",
        "CLOUD",
        "DA",
        "DE",
        "EMB",
        "FE",
        "TEST",
    ]
    matrix = metrics["main_model"]["confusion_matrix"]

    fig, axis = plt.subplots(figsize=(7.4, 6.2), dpi=180)
    fig.patch.set_facecolor(BACKGROUND)
    axis.set_facecolor(BACKGROUND)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "matte_gray",
        ["#F7F6F2", "#E8E7E2", "#D8D8D2", "#C3C5C0"],
    )
    image = axis.imshow(matrix, cmap=cmap, interpolation="nearest")
    axis.set_xticks(range(len(labels)), labels, color=MUTED, fontsize=9)
    axis.set_yticks(range(len(labels)), labels, color=MUTED, fontsize=9)
    axis.set_xlabel("Predicted role family", color=MUTED, fontsize=10, labelpad=9)
    axis.set_ylabel("Actual role family", color=MUTED, fontsize=10, labelpad=9)
    axis.set_title(
        "Grouped 5-fold confusion matrix (n=134)",
        color=INK,
        fontsize=12,
        pad=12,
        family="DejaVu Sans",
    )
    for row in range(len(matrix)):
        for column in range(len(matrix[row])):
            value = matrix[row][column]
            axis.text(
                column,
                row,
                str(value),
                ha="center",
                va="center",
                color=INK,
                fontsize=9,
                family="DejaVu Sans",
            )
    for spine in axis.spines.values():
        spine.set_color(GRID)
    colorbar = fig.colorbar(image, ax=axis, fraction=0.04, pad=0.03)
    colorbar.ax.tick_params(colors=MUTED, labelsize=8)
    colorbar.outline.set_edgecolor(GRID)
    fig.tight_layout(pad=0.8)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def draw_ranking_metrics(path: Path):
    ranking = json.loads(
        (PROJECT_ROOT / "models" / "ranking_metrics.json").read_text(encoding="utf-8")
    )
    metrics = ranking["metrics"]
    metric_names = ("Precision@3", "Recall@5", "NDCG@5")
    keys = ("precision_at_3", "recall_at_5", "ndcg_at_5")
    methods = (
        ("Keyword", "keyword"),
        ("TF-IDF", "tfidf"),
        ("Agent", "agent_hybrid"),
    )

    fig, axis = plt.subplots(figsize=(8.2, 4.8), dpi=180)
    fig.patch.set_facecolor(BACKGROUND)
    style_axes(axis)
    for (label, key), color in zip(methods, SERIES):
        values = [metrics[key][metric] for metric in keys]
        axis.plot(
            metric_names,
            values,
            color=color,
            linewidth=1.7,
            marker="o",
            markersize=4.5,
            markeredgewidth=0,
            label=label,
        )
    axis.set_ylim(0.30, 1.04)
    axis.set_ylabel("Mean score", color=MUTED, fontsize=10)
    axis.set_title(
        "Ranking baselines on 9 eligible persona queries",
        color=INK,
        fontsize=12,
        pad=12,
        family="DejaVu Sans",
    )
    axis.tick_params(axis="x", length=0, pad=8)
    legend = axis.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
        frameon=False,
        handlelength=1.8,
        columnspacing=2.2,
        fontsize=9,
    )
    for text in legend.get_texts():
        text.set_color(MUTED)
    fig.tight_layout(pad=0.8)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "system_workflow.png": draw_workflow,
        "confusion_matrix.png": draw_confusion_matrix,
        "ranking_metrics.png": draw_ranking_metrics,
    }
    for name, renderer in outputs.items():
        destination = FIGURE_DIR / name
        renderer(destination)
        print(destination)


if __name__ == "__main__":
    main()
