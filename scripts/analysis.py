"""Water quality of the Ybbs at Amstetten (Lower Austria), 2016–2026.

Monthly GZÜV monitoring data from WISA. Run scripts/prepare_data.py first.
Outputs tables to data/processed/ and figures to figures/.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, NullFormatter
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "ybbs_amstetten_2016_2026.csv"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"

LABELS = {
    "water_temp_c": "Water temperature (°C)",
    "do_mg_l": "Dissolved oxygen (mg/L)",
    "do_saturation_pct": "Oxygen saturation (%)",
    "conductivity_us_cm": "Conductivity 25 °C (µS/cm)",
    "ph": "pH",
    "bod5_mg_l": "BOD₅ (mg/L)",
    "doc_mg_l": "DOC (mg/L)",
    "suspended_solids_mg_l": "Suspended solids (mg/L)",
    "chloride_mg_l": "Chloride (mg/L)",
    "sulfate_mg_l": "Sulfate (mg/L)",
    "ammonium_n_mg_l": "Ammonium-N (mg/L)",
    "nitrate_n_mg_l": "Nitrate-N (mg/L)",
    "orthophosphate_p_mg_l": "Orthophosphate-P (mg/L)",
    "total_p_mg_l": "Total phosphorus (mg/L)",
}
BLUE, RED, GREY, DARK = "#2b6cb0", "#c53030", "#a0aec0", "#1a365d"
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def load():
    df = pd.read_csv(DATA, parse_dates=["date"])
    df = df.dropna(subset=["water_temp_c"])          # one empty sample record
    df["year"] = df.date.dt.year
    df["month"] = df.date.dt.month
    return df


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)


def do_solubility(t):
    """Oxygen solubility in fresh water at sea level (mg/L) – Benson & Krause (1984) fit."""
    return 14.62 - 0.3898 * t + 0.006969 * t**2 - 0.00005897 * t**3


# ------------------------------------------------------------------ statistics
def seasonal_kendall(df, col):
    """Seasonal Kendall trend test (Hirsch et al., 1982) with seasonal Sen slope.

    Months are the seasons; within each month, all year pairs are compared.
    Returns tau, z, p and slope (units per year).
    """
    s_total, var_total, n_pairs, slopes = 0.0, 0.0, 0, []
    for _, g in df[["year", "month", col]].dropna().groupby("month"):
        g = g.groupby("year")[col].median()          # one value per year and month
        x, y = g.index.to_numpy(float), g.to_numpy(float)
        n = len(y)
        if n < 3:
            continue
        i, j = np.triu_indices(n, k=1)
        s_total += np.sign(y[j] - y[i]).sum()
        var_total += n * (n - 1) * (2 * n + 5) / 18
        n_pairs += len(i)
        slopes.extend((y[j] - y[i]) / (x[j] - x[i]))
    z = (s_total - np.sign(s_total)) / np.sqrt(var_total) if s_total else 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return {"tau": s_total / n_pairs, "z": z, "p_value": p, "sen_slope_per_year": np.median(slopes)}


def trend_table(df):
    full_years = df[df.year <= 2025]
    rows = []
    for col in ["water_temp_c", "conductivity_us_cm", "chloride_mg_l", "sulfate_mg_l",
                "nitrate_n_mg_l", "ammonium_n_mg_l", "orthophosphate_p_mg_l", "total_p_mg_l",
                "doc_mg_l", "do_saturation_pct"]:
        r = seasonal_kendall(full_years, col)
        med = full_years[col].median()
        rows.append({
            "parameter": col,
            "median": round(med, 4),
            "kendall_tau": round(r["tau"], 3),
            "p_value": round(r["p_value"], 4),
            "sen_slope_per_year": round(r["sen_slope_per_year"], 5),
            "change_pct_per_decade": round(100 * 10 * r["sen_slope_per_year"] / med, 1),
            "significant_5pct": r["p_value"] < 0.05,
        })
    return pd.DataFrame(rows)


def cq_table(df):
    """Concentration–discharge relationship C = a·Q^b (log-log regression)."""
    rows = []
    q = df.dropna(subset=["discharge_m3s"])
    for col in ["conductivity_us_cm", "chloride_mg_l", "nitrate_n_mg_l", "doc_mg_l",
                "total_p_mg_l", "suspended_solids_mg_l"]:
        d = q[["discharge_m3s", col]].dropna()
        res = stats.linregress(np.log10(d.discharge_m3s), np.log10(d[col]))
        behaviour = ("dilution" if res.slope < -0.05 and res.pvalue < 0.05 else
                     "mobilisation" if res.slope > 0.05 and res.pvalue < 0.05 else "chemostatic")
        rows.append({"parameter": col, "n": len(d), "b_exponent": round(res.slope, 3),
                     "r2": round(res.rvalue**2, 2), "p_value": round(res.pvalue, 4),
                     "behaviour": behaviour})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------- figures
def fig_timeseries(df, path):
    cols = ["water_temp_c", "do_saturation_pct", "nitrate_n_mg_l",
            "total_p_mg_l", "chloride_mg_l", "conductivity_us_cm"]
    fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True)
    for ax, col in zip(axes.flat, cols):
        ax.plot(df.date, df[col], color=GREY, lw=0.8, marker="o", ms=2.5)
        ann = df[df.year <= 2025].groupby("year")[col].median()
        ax.step(pd.to_datetime(ann.index.astype(str) + "-07-01"), ann.values, where="mid",
                color=BLUE, lw=2, label="Annual median")
        ax.set_ylabel(LABELS[col], fontsize=9)
        if col == "total_p_mg_l":
            ax.set_yscale("log")
        style(ax)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Ybbs at Amstetten – monthly samples 2016–2026", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_seasonal(df, path):
    cols = ["water_temp_c", "do_mg_l", "nitrate_n_mg_l", "chloride_mg_l"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
    for ax, col in zip(axes.flat, cols):
        data = [df.loc[df.month == m, col].dropna() for m in range(1, 13)]
        bp = ax.boxplot(data, patch_artist=True, widths=0.6, showfliers=False,
                        medianprops={"color": "black"})
        for b in bp["boxes"]:
            b.set_facecolor(BLUE)
            b.set_alpha(0.55)
        ax.set_xticks(range(1, 13), MONTHS)
        ax.set_ylabel(LABELS[col])
        style(ax)
    fig.suptitle("Seasonal pattern (all samples by month)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_cq(df, cq, path):
    cols = ["conductivity_us_cm", "nitrate_n_mg_l", "total_p_mg_l", "suspended_solids_mg_l"]
    q = df.dropna(subset=["discharge_m3s"])
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5))
    for ax, col in zip(axes.flat, cols):
        d = q[["discharge_m3s", col]].dropna()
        r = cq.set_index("parameter").loc[col]
        ax.scatter(d.discharge_m3s, d[col], s=18, color=BLUE, alpha=0.7)
        xs = np.geomspace(d.discharge_m3s.min(), d.discharge_m3s.max(), 50)
        fit = stats.linregress(np.log10(d.discharge_m3s), np.log10(d[col]))
        ax.plot(xs, 10 ** (fit.intercept + fit.slope * np.log10(xs)), color=RED, lw=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            axis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Discharge (m³/s)")
        ax.set_ylabel(LABELS[col])
        ax.set_title(f"{r.behaviour}: b = {r.b_exponent:+.2f}, R² = {r.r2:.2f}", fontsize=9, loc="left")
        style(ax)
    fig.suptitle("Concentration–discharge relationships (C = a·Qᵇ, samples 2016–2021)",
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_oxygen(df, path):
    fig, ax = plt.subplots(figsize=(7, 4.6))
    sc = ax.scatter(df.water_temp_c, df.do_mg_l, c=df.month, cmap="twilight", s=22,
                    edgecolor="white", lw=0.3)
    t = np.linspace(df.water_temp_c.min(), df.water_temp_c.max(), 100)
    ax.plot(t, do_solubility(t), color="black", lw=1.5, label="100 % saturation")
    ax.set_xlabel(LABELS["water_temp_c"])
    ax.set_ylabel(LABELS["do_mg_l"])
    ax.set_title("Oxygen follows temperature-dependent solubility", fontweight="bold")
    ax.legend(frameon=False)
    cb = fig.colorbar(sc, ax=ax, ticks=range(1, 13))
    cb.set_label("Month")
    style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------------ main
def main():
    PROC.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(exist_ok=True)
    df = load()

    summary = df[list(LABELS)].describe(percentiles=[0.1, 0.5, 0.9]).T.round(3)
    trends = trend_table(df)
    cq = cq_table(df)
    monthly = df.groupby("month")[list(LABELS)].median().round(3)

    summary.to_csv(PROC / "summary_statistics.csv")
    trends.to_csv(PROC / "trends_seasonal_kendall.csv", index=False)
    cq.to_csv(PROC / "concentration_discharge.csv", index=False)
    monthly.to_csv(PROC / "monthly_medians.csv")

    fig_timeseries(df, FIG / "timeseries.png")
    fig_seasonal(df, FIG / "seasonal_pattern.png")
    fig_cq(df, cq, FIG / "concentration_discharge.png")
    fig_oxygen(df, FIG / "oxygen_temperature.png")

    pd.set_option("display.width", 160)
    print(f"{len(df)} samples, {df.date.min():%Y-%m-%d} – {df.date.max():%Y-%m-%d}\n")
    print(summary[["count", "10%", "50%", "90%", "max"]].to_string())
    print("\n=== Seasonal Kendall trends (2016–2025) ===")
    print(trends.to_string(index=False))
    print("\n=== Concentration–discharge (2016–2021) ===")
    print(cq.to_string(index=False))


if __name__ == "__main__":
    main()
