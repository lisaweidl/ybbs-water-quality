"""Extract core physico-chemical parameters from the WISA export into a tidy CSV.

Input:  data/raw/WISA_export_Ybbs_Amstetten_2016-2026.xlsx  (WISA H2O-Fachdatenbank export)
Output: data/raw/ybbs_amstetten_2016_2026.csv

Value conventions in WISA exports:
  [0.002]  substance not detected; number = limit of detection (LOD)
  0.0025   values below the limit of quantification are already exported as half
           the LOQ ("Halbe BG (QZV Standard)", see selection criteria)
Non-detects are set to half the LOD and flagged in <param>_flag = "<LOD".
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "WISA_export_Ybbs_Amstetten_2016-2026.xlsx"
OUT = ROOT / "data" / "raw" / "ybbs_amstetten_2016_2026.csv"

# WISA parameter code -> column name
PARAMS = {
    "F107": "discharge_m3s",
    "F117": "water_temp_c",
    "F118": "conductivity_us_cm",      # at 25 °C
    "F119": "ph",
    "F124": "do_mg_l",
    "F125": "do_saturation_pct",
    "F126": "bod5_mg_l",
    "F130": "doc_mg_l",
    "F133": "suspended_solids_mg_l",
    "F143": "calcium_mg_l",
    "F145": "sodium_mg_l",
    "F177": "chloride_mg_l",
    "F178": "sulfate_mg_l",
    "F173": "ammonium_n_mg_l",
    "F175": "nitrite_n_mg_l",
    "F176": "nitrate_n_mg_l",
    "F183": "orthophosphate_p_mg_l",
    "F271": "total_p_mg_l",            # unfiltered
}
WITH_FLAG = ["bod5_mg_l", "suspended_solids_mg_l", "ammonium_n_mg_l", "nitrite_n_mg_l",
             "orthophosphate_p_mg_l", "total_p_mg_l"]


def parse(v):
    """Return (value, flag)."""
    if pd.isna(v):
        return np.nan, ""
    s = str(v).strip().replace(",", ".")
    if s.startswith("[") and s.endswith("]"):
        return float(s[1:-1]) / 2, "<LOD"
    if s.startswith("<"):
        return float(s[1:]) / 2, "<LOQ"
    try:
        return float(s), ""
    except ValueError:
        return np.nan, ""


def main():
    raw = pd.read_excel(SRC, sheet_name="Daten Ebene 1 und Stammdaten", header=None)
    codes = raw.iloc[1].astype(str).str.split().str[0]
    data = raw.iloc[3:].reset_index(drop=True)
    data = data[data[0] != "-STAMMDATEN-"]

    out = pd.DataFrame({
        "sample_id": data[0].values,
        "station_id": data[2].values,
        "station": data[3].values,
        "river": data[4].values,
        "date": pd.to_datetime(data[5]).dt.date.values,
    })
    for code, name in PARAMS.items():
        col = codes[codes == code].index[0]
        parsed = data[col].map(parse)
        out[name] = [p[0] for p in parsed]
        if name in WITH_FLAG:
            out[f"{name}_flag"] = [p[1] for p in parsed]

    out = out.sort_values("date").reset_index(drop=True)
    out.to_csv(OUT, index=False)
    print(f"{len(out)} samples, {out.date.min()} – {out.date.max()} -> {OUT.name}")
    print(out.drop(columns=[c for c in out.columns if c.endswith("_flag")]).describe().T.round(3))


if __name__ == "__main__":
    main()
