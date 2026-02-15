#!/usr/bin/env python3
"""
Transform CMS HHA cost report CSVs into:
  1. providers_annual.csv - one row per provider (CCN) per year, with operator_id
  2. operators_annual.csv - one row per operator per year, financials rolled up
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path(__file__).resolve().parent
YEARS = (2020, 2021, 2022, 2023)
CBSA_ZIP_CROSSWALK_PATH = PROJECT_DIR / "cbsa_zip_crosswalk.csv"

# Columns to include in providers_annual (identity, location, ownership, fiscal, volume, cost, revenue, income, balance sheet)
PROVIDER_COLUMNS = [
    "rpt_rec_num",
    "Provider CCN",
    "HHA Name",
    "Street Address",
    "City",
    "State Code",
    "Zip Code",
    "Type of Control",
    "Fiscal Year Begin Date",
    "Fiscal Year End Date",
    "HHA-based Hospice Provider CCN",
    "Total, Medicare Title XVIII Visits",
    "Total, Medicaid Title XIX Visits",
    "Total, Other Visits",
    "Total, Total Visits",
    "Total Episodes-Total Visits",
    "Total Episodes-Total Charges",
    "Total Cost",
    "Total HHA Medicare Program Visits",
    "Total HHA Medicare Program Cost",
    "Gross Patient Revenues Title XVIII Medicare",
    "Gross Patient Revenues Title XIX Medicaid",
    "Gross Patient Revenues Other",
    "Gross Patient Revenues Total",
    "Less: Allowances and discounts on patients' accounts Title XVIII Medicare",
    "Less: Allowances and discounts on patients' accounts Title XIX Medicaid",
    "Less: Allowances and discounts on patients' accounts Other",
    "Less: Allowances and discounts on patients' accounts Total",
    "Net Patient Revenues (line 1 minus line 2) XVIII Medicare",
    "Net Patient Revenues (line 1 minus line 2) XIX Medicaid",
    "Net Patient Revenues (line 1 minus line 2) Other",
    "Net Patient Revenues (line 1 minus line 2) Total",
    "Less Total Operating Expenses (sum of lines 4 through 16)",
    "Net Income from service to patients (line 3 minus line 17)",
    "Total Other Income (sum of lines 19 through 31)",
    "Net Income or Loss for the period (line 18 plus line 32)",
    "Total PPS Payment - full episodes/periods without outliers",
    "Total PPS Payment - full episodes/periods with outliers",
    "Total PPS Payment - LUPA episodes/periods",
    "Total PPS Payment - PEP episodes/periods",
    "Total PPS Outlier Payment - full episodes/periods with outliers",
    "Total PPS Outlier Payment - PEP episodes/periods",
    "Allowable Bad Debts",
    "Adjusted Reimbursable Bad Debts",
    "Total Current Assets",
    "Total Fixed Assets",
    "Total Assets",
    "Total Current Liabilities",
    "Total Long Term Liabilities",
    "Total Liabilities",
    "Fund Balance",
    "Total Liabilities and Fund Balances",
    "Total Hospice Days Title XVIII Medicare",
    "Total Hospice Days Title XIX Medicaid",
    "Total Hospice Days Title Other",
    "Total Hospice Days Total",
    "Total Hospice Expenses",
]


def normalize_operator_name(name: str) -> str:
    """Normalize HHA name for grouping into operators (multi-site)."""
    if not name or not name.strip():
        return ""
    s = name.strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s


def safe_float(val, default=None):
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    try:
        s = str(val).replace(",", "").strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def normalize_zip(zip_val) -> str:
    """Normalize to 5-digit string for crosswalk lookup."""
    if zip_val is None:
        return ""
    s = re.sub(r"\D", "", str(zip_val).strip())
    return s[:5].zfill(5) if len(s) >= 5 else ""


def load_zip_to_cbsa(path: Path) -> dict[str, str]:
    """Load cbsa_zip_crosswalk; return dict zip_5char -> cbsa (str). For ZIPs in multiple CBSAs, keep the one with max TOT_RATIO."""
    if not path.exists():
        return {}
    zip_best: dict[str, tuple[float, str]] = {}  # zip -> (tot_ratio, cbsa)
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            zip_s = normalize_zip(row.get("ZIP"))
            if not zip_s:
                continue
            cbsa = (row.get("CBSA") or "").strip()
            if not cbsa:
                continue
            try:
                tot = float((row.get("TOT_RATIO") or "0").strip())
            except (ValueError, TypeError):
                tot = 0.0
            if zip_s not in zip_best or tot > zip_best[zip_s][0]:
                zip_best[zip_s] = (tot, cbsa)
    return {z: cbsa for z, (_, cbsa) in zip_best.items()}


def load_year(path: Path) -> tuple[list[str], list[dict]]:
    """Return (headers, list of row dicts)."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        headers = r.fieldnames or []
        rows = list(r)
    return headers, rows


def main():
    # 1) Load all years and build global normalized name -> operator_id
    all_rows_by_year: dict[int, list[dict]] = {}
    normalized_to_id: dict[str, int] = {}
    next_operator_id = 1

    for year in YEARS:
        path = PROJECT_DIR / str(year) / f"CostReporthha_Final_{year % 100:02d}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        headers, rows = load_year(path)
        for row in rows:
            name = (row.get("HHA Name") or "").strip()
            norm = normalize_operator_name(name)
            if norm and norm not in normalized_to_id:
                normalized_to_id[norm] = next_operator_id
                next_operator_id += 1
        all_rows_by_year[year] = rows

    # Load ZIP -> CBSA crosswalk for provider/operator CBSA
    zip_to_cbsa = load_zip_to_cbsa(CBSA_ZIP_CROSSWALK_PATH)

    # 2) Build providers_annual: one row per (CCN, year) with selected columns + operator_id, year, cbsa_cd
    provider_headers = ["year", "operator_id", "HHA Name"]
    for c in PROVIDER_COLUMNS:
        if c == "HHA Name":
            continue
        provider_headers.append(c)
        if c == "Zip Code":
            provider_headers.append("cbsa_cd")
    provider_out_path = PROJECT_DIR / "providers_annual.csv"

    with open(provider_out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=provider_headers, extrasaction="ignore")
        w.writeheader()

        for year in YEARS:
            rows = all_rows_by_year[year]
            for row in rows:
                name = (row.get("HHA Name") or "").strip()
                norm = normalize_operator_name(name)
                operator_id = normalized_to_id.get(norm, "")

                out = {"year": year, "operator_id": operator_id if operator_id else ""}
                for col in PROVIDER_COLUMNS:
                    if col in row:
                        out[col] = row[col]
                out["cbsa_cd"] = zip_to_cbsa.get(normalize_zip(row.get("Zip Code")), "")
                w.writerow(out)

    print(f"Wrote {provider_out_path} with {sum(len(all_rows_by_year[y]) for y in YEARS)} rows")

    # 3) Build operators_annual: one row per (operator_id, year) with rolled-up financials
    # Sum: revenue, cost, visits, income, assets, liabilities; count: CCNs, states; canonical name
    sum_cols = [
        "Gross Patient Revenues Title XVIII Medicare",
        "Gross Patient Revenues Title XIX Medicaid",
        "Gross Patient Revenues Other",
        "Gross Patient Revenues Total",
        "Net Patient Revenues (line 1 minus line 2) XVIII Medicare",
        "Net Patient Revenues (line 1 minus line 2) XIX Medicaid",
        "Net Patient Revenues (line 1 minus line 2) Other",
        "Net Patient Revenues (line 1 minus line 2) Total",
        "Total Cost",
        "Total HHA Medicare Program Cost",
        "Total, Total Visits",
        "Total Episodes-Total Visits",
        "Total Episodes-Total Charges",
        "Less Total Operating Expenses (sum of lines 4 through 16)",
        "Net Income from service to patients (line 3 minus line 17)",
        "Net Income or Loss for the period (line 18 plus line 32)",
        "Total Assets",
        "Total Liabilities",
        "Fund Balance",
        "Total PPS Payment - full episodes/periods without outliers",
        "Total PPS Payment - full episodes/periods with outliers",
        "Total PPS Payment - LUPA episodes/periods",
        "Total PPS Payment - PEP episodes/periods",
        "Total Hospice Days Total",
        "Total Hospice Expenses",
    ]

    operator_headers = [
        "year",
        "operator_id",
        "operator_name",
        "n_ccns",
        "n_states",
        "state_codes",
        "cbsa_codes",
    ] + sum_cols

    agg_by_key: dict[tuple[int, int], dict] = defaultdict(lambda: {k: 0.0 for k in sum_cols})
    names_by_key: dict[tuple[int, int], list[str]] = defaultdict(list)
    ccns_by_key: dict[tuple[int, int], set] = defaultdict(set)
    states_by_key: dict[tuple[int, int], set] = defaultdict(set)
    cbsas_by_key: dict[tuple[int, int], set] = defaultdict(set)

    for year in YEARS:
        for row in all_rows_by_year[year]:
            name = (row.get("HHA Name") or "").strip()
            norm = normalize_operator_name(name)
            operator_id = normalized_to_id.get(norm)
            if not operator_id:
                continue
            key = (year, operator_id)
            names_by_key[key].append(name)
            ccns_by_key[key].add((row.get("Provider CCN") or "").strip())
            state = (row.get("State Code") or "").strip()
            if state:
                states_by_key[key].add(state)
            cbsa = zip_to_cbsa.get(normalize_zip(row.get("Zip Code")), "")
            if cbsa:
                cbsas_by_key[key].add(cbsa)
            for col in sum_cols:
                val = safe_float(row.get(col), 0)
                if val is not None:
                    agg_by_key[key][col] = agg_by_key[key].get(col, 0) + val

    operator_out_path = PROJECT_DIR / "operators_annual.csv"
    with open(operator_out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=operator_headers)
        w.writeheader()
        for (year, operator_id), sums in sorted(agg_by_key.items()):
            names = names_by_key.get((year, operator_id), [])
            operator_name = max(set(names), key=names.count) if names else ""
            ccns = ccns_by_key.get((year, operator_id), set())
            states = sorted(states_by_key.get((year, operator_id), set()))
            cbsas = sorted(cbsas_by_key.get((year, operator_id), set()))
            row = {
                "year": year,
                "operator_id": operator_id,
                "operator_name": operator_name,
                "n_ccns": len(ccns),
                "n_states": len(states),
                "state_codes": "|".join(states) if states else "",
                "cbsa_codes": "|".join(cbsas) if cbsas else "",
            }
            for col in sum_cols:
                row[col] = sums.get(col, 0)
            w.writerow(row)

    print(f"Wrote {operator_out_path} with {len(agg_by_key)} rows")


if __name__ == "__main__":
    main()
