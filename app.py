"""
HHA Dashboard: Operators table and Dashboard tab with filters.
Uses providers_annual.csv and operators_annual.csv.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import zipfile
import io
import requests
import altair as alt

PROJECT_DIR = Path(__file__).resolve().parent
OPERATORS_PATH = PROJECT_DIR / "operators_annual.csv"
PROVIDERS_PATH = PROJECT_DIR / "providers_annual.csv"

# CMS Type of Control codes (HHA/cost report standard). Source: CMS cost report instructions.
TOC_CODE_TO_LABEL = {
    "1": "Voluntary Nonprofit-Church",
    "2": "Voluntary Nonprofit-Other",
    "3": "Proprietary-Individual",
    "4": "Proprietary-Corporation",
    "5": "Proprietary-Partnership",
    "6": "Proprietary-Other",
    "7": "Governmental-Federal",
    "8": "Governmental-City-County",
    "9": "Governmental-County",
    "10": "Governmental-State",
    "11": "Governmental-Hospital District",
    "12": "Governmental-City",
    "13": "Governmental-Other",
}
ORDERED_OWNERSHIP_LABELS = list(TOC_CODE_TO_LABEL.values())

# All US state abbreviations for choropleth (include DC)
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# State FIPS codes (numeric) for Altair US states TopoJSON (vega us-10m)
STATE_TO_FIPS = {
    "AL": 1, "AK": 2, "AZ": 4, "AR": 5, "CA": 6, "CO": 8, "CT": 9, "DE": 10,
    "DC": 11, "FL": 12, "GA": 13, "HI": 15, "ID": 16, "IL": 17, "IN": 18, "IA": 19,
    "KS": 20, "KY": 21, "LA": 22, "ME": 23, "MD": 24, "MA": 25, "MI": 26, "MN": 27,
    "MS": 28, "MO": 29, "MT": 30, "NE": 31, "NV": 32, "NH": 33, "NJ": 34, "NM": 35,
    "NY": 36, "NC": 37, "ND": 38, "OH": 39, "OK": 40, "OR": 41, "PA": 42, "RI": 44,
    "SC": 45, "SD": 46, "TN": 47, "TX": 48, "UT": 49, "VT": 50, "VA": 51, "WA": 53,
    "WV": 54, "WI": 55, "WY": 56,
}
US_10M_URL = "https://cdn.jsdelivr.net/npm/vega-datasets@2/data/us-10m.json"


@st.cache_data
def load_operators() -> pd.DataFrame:
    return pd.read_csv(OPERATORS_PATH)


@st.cache_data
def load_providers() -> pd.DataFrame:
    return pd.read_csv(PROVIDERS_PATH)


def _normalize_toc_code(toc) -> str:
    """Normalize Type of Control to integer string (e.g. 5.0 -> '5') for consistent mapping."""
    if not pd.notna(toc) or str(toc).strip() in ("", "nan", "NaN"):
        return ""
    s = str(toc).strip()
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return s


def _ownership_label(toc: str) -> str:
    """Map CMS Type of Control code to detailed ownership label (or 'Other' for unknown/blank)."""
    code = _normalize_toc_code(toc)
    if not code:
        return "Other"
    return TOC_CODE_TO_LABEL.get(code, "Other")


MEDICARE_REV_COL = "Gross Patient Revenues Title XVIII Medicare"
MEDICARE_NET_REV_COL = "Net Patient Revenues (line 1 minus line 2) XVIII Medicare"
MEDICAID_REV_COL = "Gross Patient Revenues Title XIX Medicaid"
MEDICAID_NET_REV_COL = "Net Patient Revenues (line 1 minus line 2) XIX Medicaid"


@st.cache_data
def build_enriched_operators(
    operators: pd.DataFrame,
    providers: pd.DataFrame,
) -> pd.DataFrame:
    """Add revenue_growth_pct, net_income_margin_pct, medicare_revenue_growth_pct, medicare_net_income_margin_pct, ownership."""
    rev_col = "Gross Patient Revenues Total"
    ni_col = "Net Income or Loss for the period (line 18 plus line 32)"

    # Prior-year revenue (total)
    prior = operators[["operator_id", "year", rev_col]].copy()
    prior["year"] = prior["year"] + 1
    prior = prior.rename(columns={rev_col: "prior_year_revenue"})
    op = operators.merge(prior, on=["operator_id", "year"], how="left")
    op["prior_year_revenue"] = pd.to_numeric(op["prior_year_revenue"], errors="coerce")
    op[rev_col] = pd.to_numeric(op[rev_col], errors="coerce")
    op["revenue_growth_pct"] = None
    mask = op["prior_year_revenue"].notna() & (op["prior_year_revenue"] > 0)
    op.loc[mask, "revenue_growth_pct"] = (
        (op.loc[mask, rev_col] - op.loc[mask, "prior_year_revenue"])
        / op.loc[mask, "prior_year_revenue"]
        * 100
    )
    op = op.drop(columns=["prior_year_revenue"])

    # Prior-year Medicare revenue
    prior_med = operators[["operator_id", "year", MEDICARE_REV_COL]].copy()
    prior_med["year"] = prior_med["year"] + 1
    prior_med = prior_med.rename(columns={MEDICARE_REV_COL: "prior_medicare_revenue"})
    op = op.merge(prior_med, on=["operator_id", "year"], how="left")
    op["prior_medicare_revenue"] = pd.to_numeric(op["prior_medicare_revenue"], errors="coerce")
    op[MEDICARE_REV_COL] = pd.to_numeric(op[MEDICARE_REV_COL], errors="coerce")
    op["medicare_revenue_growth_pct"] = None
    mask_med = op["prior_medicare_revenue"].notna() & (op["prior_medicare_revenue"] > 0)
    op.loc[mask_med, "medicare_revenue_growth_pct"] = (
        (op.loc[mask_med, MEDICARE_REV_COL] - op.loc[mask_med, "prior_medicare_revenue"])
        / op.loc[mask_med, "prior_medicare_revenue"]
        * 100
    )
    op = op.drop(columns=["prior_medicare_revenue"])

    # Net income margin (total)
    op[ni_col] = pd.to_numeric(op[ni_col], errors="coerce")
    op["net_income_margin_pct"] = None
    rev_pos = op[rev_col].notna() & (op[rev_col] > 0)
    op.loc[rev_pos, "net_income_margin_pct"] = (
        op.loc[rev_pos, ni_col] / op.loc[rev_pos, rev_col] * 100
    )

    # Medicare net income margin
    op[MEDICARE_NET_REV_COL] = pd.to_numeric(op[MEDICARE_NET_REV_COL], errors="coerce")
    op["medicare_net_income_margin_pct"] = None
    med_rev_pos = op[MEDICARE_REV_COL].notna() & (op[MEDICARE_REV_COL] > 0)
    op.loc[med_rev_pos, "medicare_net_income_margin_pct"] = (
        op.loc[med_rev_pos, MEDICARE_NET_REV_COL] / op.loc[med_rev_pos, MEDICARE_REV_COL] * 100
    )

    # Ownership from providers: mode of Type of Control per (operator_id, year)
    # Map to detailed CMS label (e.g. Proprietary-Corporation, Governmental-State)
    prov = providers[["operator_id", "year", "Type of Control"]].copy()
    prov["toc_code"] = prov["Type of Control"].map(_normalize_toc_code)
    prov = prov[prov["toc_code"] != ""]  # drop blank so mode is meaningful
    mode_toc = (
        prov.groupby(["operator_id", "year"])["toc_code"]
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) else "")
        .reset_index()
        .rename(columns={"toc_code": "ownership"})
    )
    mode_toc["ownership"] = mode_toc["ownership"].map(_ownership_label)
    op = op.merge(mode_toc, on=["operator_id", "year"], how="left")
    op["ownership"] = op["ownership"].fillna("Other")

    return op


def apply_filters(
    df: pd.DataFrame,
    year: int,
    states: list[str],
    ownerships: list[str],
    revenue_min: float | None,
    revenue_max: float | None,
    net_income_min: float | None,
    net_income_max: float | None,
    margin_min: float | None,
    margin_max: float | None,
    name_substring: str | None = None,
    city_substring: str | None = None,
    zip_substring: str | None = None,
    providers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rev_col = "Gross Patient Revenues Total"
    ni_col = "Net Income or Loss for the period (line 18 plus line 32)"

    out = df[df["year"] == year].copy()
    if states:
        out = out[out["state_codes"].str.split("|").map(lambda x: any(s in (x or []) for s in states))]
    if ownerships:
        out = out[out["ownership"].isin(ownerships)]
    if name_substring and name_substring.strip():
        out = out[
            out["operator_name"].astype(str).str.contains(name_substring.strip(), case=False, na=False)
        ]
    if city_substring and city_substring.strip() and providers is not None:
        prov_year = providers[providers["year"] == year].copy()
        prov_year["City"] = prov_year["City"].astype(str)
        match = prov_year["City"].str.contains(city_substring.strip(), case=False, na=False)
        operator_ids_in_city = prov_year.loc[match, "operator_id"].dropna().unique()
        out = out[out["operator_id"].isin(operator_ids_in_city)]
    if zip_substring and zip_substring.strip() and providers is not None:
        prov_year = providers[providers["year"] == year].copy()
        prov_year["Zip Code"] = prov_year["Zip Code"].astype(str)
        match = prov_year["Zip Code"].str.contains(zip_substring.strip(), case=False, na=False)
        operator_ids_in_zip = prov_year.loc[match, "operator_id"].dropna().unique()
        out = out[out["operator_id"].isin(operator_ids_in_zip)]
    if revenue_min is not None:
        out = out[pd.to_numeric(out[rev_col], errors="coerce") >= revenue_min]
    if revenue_max is not None:
        out = out[pd.to_numeric(out[rev_col], errors="coerce") <= revenue_max]
    if net_income_min is not None:
        out = out[pd.to_numeric(out[ni_col], errors="coerce") >= net_income_min]
    if net_income_max is not None:
        out = out[pd.to_numeric(out[ni_col], errors="coerce") <= net_income_max]
    if margin_min is not None:
        out = out[out["net_income_margin_pct"].notna() & (out["net_income_margin_pct"] >= margin_min)]
    if margin_max is not None:
        out = out[out["net_income_margin_pct"].notna() & (out["net_income_margin_pct"] <= margin_max)]
    return out


ZIP_CENTROID_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_zcta_national.zip"
ZIP_LAT_LON_PATH = PROJECT_DIR / "zip_lat_lon.csv"


def _load_zip_centroids_uncached() -> pd.DataFrame | None:
    """Load zip code -> (lat, lon). Tries local zip_lat_lon.csv, then Census 2020 ZCTA gazetteer."""
    if ZIP_LAT_LON_PATH.exists():
        df = pd.read_csv(ZIP_LAT_LON_PATH)
        # Normalize column names (allow zip/lat/lon in any case)
        df = df.rename(columns={c: c.lower() for c in df.columns})
        if not all(k in df.columns for k in ("zip", "lat", "lon")):
            return None
        df["zip"] = df["zip"].astype(str).str.strip().str[:5]
        df = df.dropna(subset=["lat", "lon"])
        return df[["zip", "lat", "lon"]].drop_duplicates(subset=["zip"])
    try:
        r = requests.get(ZIP_CENTROID_URL, timeout=30)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            name = [n for n in z.namelist() if n.endswith(".txt")][0]
            with z.open(name) as f:
                tab = pd.read_csv(f, sep="\t", dtype=str, on_bad_lines="skip")
        tab = tab.rename(columns={"GEOID": "zip", "INTPTLAT": "lat", "INTPTLONG": "lon"})
        tab["zip"] = tab["zip"].str.strip().str[:5]
        tab["lat"] = pd.to_numeric(tab["lat"], errors="coerce")
        tab["lon"] = pd.to_numeric(tab["lon"], errors="coerce")
        tab = tab.dropna(subset=["lat", "lon"])[["zip", "lat", "lon"]].drop_duplicates(subset=["zip"])
        return tab
    except Exception:
        return None


@st.cache_data
def load_zip_centroids(_cache_key: float = 0) -> pd.DataFrame | None:
    """Load zip code -> (lat, lon). Cache key from local file mtime so cache invalidates when file is added/updated."""
    return _load_zip_centroids_uncached()


def state_revenue_from_providers(providers: pd.DataFrame, year: int, states: list[str] | None) -> pd.DataFrame:
    """State-level revenue from providers_annual only (no double-counting)."""
    rev_col = "Gross Patient Revenues Total"
    df = providers[providers["year"] == year].copy()
    df[rev_col] = pd.to_numeric(df[rev_col], errors="coerce").fillna(0)
    if states:
        df = df[df["State Code"].isin(states)]
    by_state = df.groupby("State Code", as_index=False)[rev_col].sum()
    # Ensure all US states present for map (fill 0)
    all_states_df = pd.DataFrame({"State Code": US_STATES})
    by_state = all_states_df.merge(by_state, on="State Code", how="left").fillna(0)
    return by_state


def format_currency(x) -> str:
    if pd.isna(x) or x == 0:
        return "$0"
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:.2f}K"
    return f"${x:.2f}"


def make_pareto_altair(
    values: pd.Series,
    value_label: str,
    title: str,
    value_scale: float = 1.0,
    value_suffix: str = "",
):
    """Build a Pareto chart with Altair: bars (value, sorted desc) + cumulative % line."""
    s = values.dropna()
    s = s[s > 0] if value_scale != 1 else s
    if len(s) == 0:
        return None
    s = s.sort_values(ascending=False).reset_index(drop=True)
    s = s / value_scale
    total = s.sum()
    cum_pct = (s.cumsum() / total * 100) if total else s * 0
    df = pd.DataFrame({"rank": s.index + 1, "value": s.values, "cum_pct": cum_pct.values})
    bar = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            alt.X("rank:O", title="Rank (by value)"),
            alt.Y("value:Q", title=f"{value_label} ({value_suffix})"),
        )
    )
    line = (
        alt.Chart(df)
        .mark_line(color="firebrick", strokeDash=[4, 2])
        .encode(
            alt.X("rank:O", title="Rank (by value)"),
            alt.Y("cum_pct:Q", title="Cumulative %"),
        )
    )
    chart = (
        alt.layer(bar, line)
        .resolve_scale(y="independent")
        .properties(title=title)
    )
    return chart


def main():
    st.set_page_config(page_title="HHA Dashboard", layout="wide")
    st.title("Home Health Agency Dashboard")

    st.markdown(
        "This dashboard is powered by data from the [CMS Home Health Agency Cost Report](https://data.cms.gov/provider-compliance/cost-reports/home-health-agency-cost-report) "
        "for **2020 through 2023**. The financial data reflects what each provider reported to Medicare as part of the "
        "requirements for Medicare participation. **Medicare revenue** data should generally be treated as trustworthy, "
        "whereas other reported revenue and cost data is less likely to be audited and should be treated with greater caution."
    )

    operators_raw = load_operators()
    providers_raw = load_providers()
    enriched = build_enriched_operators(operators_raw, providers_raw)

    # Sidebar filters
    st.sidebar.header("Filters")
    year = st.sidebar.selectbox("Year", [2020, 2021, 2022, 2023], index=3)

    all_states = sorted(
        set(
            s
            for codes in enriched["state_codes"].dropna().unique()
            for s in (codes or "").split("|")
            if s.strip()
        )
    )
    states = st.sidebar.multiselect("State (operator has at least one CCN in)", all_states, default=[])

    # Ordered: nonprofit, proprietary, governmental; plus Other for unknown/blank
    ownership_options = ORDERED_OWNERSHIP_LABELS + ["Other"]
    ownerships = st.sidebar.multiselect("Ownership", ownership_options, default=[])

    name_filter = st.sidebar.text_input("Name (operator name contains)", placeholder="e.g. BAYADA")
    city_filter = st.sidebar.text_input("City (operator has a site in city containing)", placeholder="e.g. Miami")
    zip_filter = st.sidebar.text_input("Zip code (operator has a site in zip containing)", placeholder="e.g. 330")

    rev_col = "Gross Patient Revenues Total"
    revenue_min = st.sidebar.number_input("Revenue min ($)", min_value=0, value=None, step=100000, format="%d")
    revenue_max = st.sidebar.number_input("Revenue max ($)", min_value=0, value=None, step=100000, format="%d")

    ni_col = "Net Income or Loss for the period (line 18 plus line 32)"
    net_income_min = st.sidebar.number_input("Net income min ($)", value=None, step=10000, format="%d")
    net_income_max = st.sidebar.number_input("Net income max ($)", value=None, step=10000, format="%d")

    margin_min = st.sidebar.number_input("Net income margin min (%)", value=None, step=1.0, format="%f")
    margin_max = st.sidebar.number_input("Net income margin max (%)", value=None, step=1.0, format="%f")

    filtered = apply_filters(
        enriched,
        year=year,
        states=states,
        ownerships=ownerships,
        revenue_min=revenue_min,
        revenue_max=revenue_max,
        net_income_min=net_income_min,
        net_income_max=net_income_max,
        margin_min=margin_min,
        margin_max=margin_max,
        name_substring=name_filter or None,
        city_substring=city_filter or None,
        zip_substring=zip_filter or None,
        providers=providers_raw,
    )

    tab1, tab2 = st.tabs(["Operators", "Dashboard"])

    with tab1:
        st.subheader("Operators table")
        # Cities from providers (selected year): unique cities per operator, comma-separated
        prov_year = providers_raw[providers_raw["year"] == year][["operator_id", "City"]].copy()
        prov_year["City"] = prov_year["City"].astype(str).str.strip()
        prov_year = prov_year[prov_year["City"].str.len() > 0]
        cities_agg = (
            prov_year.groupby("operator_id")["City"]
            .apply(lambda x: ", ".join(sorted(x.unique())))
            .reset_index()
            .rename(columns={"City": "cities"})
        )
        table_df = filtered.merge(cities_agg, on="operator_id", how="left")
        table_df["cities"] = table_df["cities"].fillna("")
        display_cols = [
            "operator_id",
            "operator_name",
            "state_codes",
            "cities",
            "ownership",
            rev_col,
            ni_col,
            "net_income_margin_pct",
            "revenue_growth_pct",
            MEDICARE_REV_COL,
            MEDICARE_NET_REV_COL,
            "medicare_net_income_margin_pct",
            "medicare_revenue_growth_pct",
        ]
        table_df = table_df[display_cols].copy()
        table_df = table_df.rename(columns={
            "state_codes": "States",
            "cities": "Cities",
            "ownership": "Type of control",
            rev_col: "Total revenue",
            MEDICARE_REV_COL: "Medicare revenue",
            MEDICARE_NET_REV_COL: "Medicare net income",
            "medicare_net_income_margin_pct": "Medicare net income margin (%)",
            "medicare_revenue_growth_pct": "Medicare revenue growth (%)",
            ni_col: "Net income",
            "net_income_margin_pct": "Net income margin (%)",
            "revenue_growth_pct": "Revenue growth (%)",
        })
        table_df["States"] = table_df["States"].str.replace("|", ", ", regex=False)
        st.dataframe(table_df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Summary metrics")
        n_op = len(filtered)
        total_rev = pd.to_numeric(filtered[rev_col], errors="coerce").sum()
        total_medicare = pd.to_numeric(filtered[MEDICARE_REV_COL], errors="coerce").sum()
        total_medicaid = pd.to_numeric(filtered[MEDICAID_REV_COL], errors="coerce").sum()
        margin_series = filtered["net_income_margin_pct"].dropna()
        avg_margin = margin_series.mean() if len(margin_series) else None
        medicare_rev = pd.to_numeric(filtered[MEDICARE_REV_COL], errors="coerce")
        medicare_net = pd.to_numeric(filtered[MEDICARE_NET_REV_COL], errors="coerce")
        medicaid_rev = pd.to_numeric(filtered[MEDICAID_REV_COL], errors="coerce")
        medicaid_net = pd.to_numeric(filtered[MEDICAID_NET_REV_COL], errors="coerce")
        _medicare_margin = medicare_net / medicare_rev * 100
        medicare_margin_series = _medicare_margin.where(np.isfinite(_medicare_margin))[(medicare_rev > 0)].dropna()
        _medicaid_margin = medicaid_net / medicaid_rev * 100
        medicaid_margin_series = _medicaid_margin.where(np.isfinite(_medicaid_margin))[(medicaid_rev > 0)].dropna()
        avg_medicare_margin = medicare_margin_series.mean() if len(medicare_margin_series) else None
        avg_medicaid_margin = medicaid_margin_series.mean() if len(medicaid_margin_series) else None

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Operators", f"{n_op:,}")
        c2.metric("Total revenue", format_currency(total_rev))
        c3.metric("Total Medicare revenue", format_currency(total_medicare))
        c4.metric("Total Medicaid revenue", format_currency(total_medicaid))
        c5.metric("Avg net income margin (%)", f"{avg_margin:.1f}%" if avg_margin is not None else "—")
        c6.metric("Avg Medicare net income margin (%)", f"{avg_medicare_margin:.1f}%" if avg_medicare_margin is not None else "—")
        c7.metric("Avg Medicaid net income margin (%)", f"{avg_medicaid_margin:.1f}%" if avg_medicaid_margin is not None else "—")

        st.subheader("Distributions")
        rev_numeric = pd.to_numeric(filtered[rev_col], errors="coerce").dropna()
        rev_numeric = rev_numeric[rev_numeric >= 0]
        medicare_numeric = pd.to_numeric(filtered["Gross Patient Revenues Title XVIII Medicare"], errors="coerce").dropna()
        medicare_numeric = medicare_numeric[medicare_numeric >= 0]
        medicaid_numeric = pd.to_numeric(filtered["Gross Patient Revenues Title XIX Medicaid"], errors="coerce").dropna()
        medicaid_numeric = medicaid_numeric[medicaid_numeric >= 0]

        REVENUE_BUCKETS = [
            "$0",
            "$0–$100k",
            "$100k–$500k",
            "$500k–$1M",
            "$1M–$2M",
            "$2M–$5M",
            "$5M–$10M",
            "$10M–$50M",
            "$50M+",
        ]

        def _revenue_bucket(value: float) -> str:
            if value == 0:
                return "$0"
            if value <= 100_000:
                return "$0–$100k"
            if value <= 500_000:
                return "$100k–$500k"
            if value <= 1e6:
                return "$500k–$1M"
            if value <= 2e6:
                return "$1M–$2M"
            if value <= 5e6:
                return "$2M–$5M"
            if value <= 10e6:
                return "$5M–$10M"
            if value <= 50e6:
                return "$10M–$50M"
            return "$50M+"

        def _altair_revenue_bars(series: pd.Series, title: str) -> alt.Chart | None:
            if series.empty:
                return None
            bucketed = series.map(_revenue_bucket)
            counts = bucketed.value_counts().reindex(REVENUE_BUCKETS, fill_value=0).reset_index()
            counts.columns = ["bucket", "count"]
            return (
                alt.Chart(counts)
                .mark_bar()
                .encode(
                    alt.X("bucket:N", sort=REVENUE_BUCKETS, title="Revenue"),
                    alt.Y("count:Q", title="Count of operators"),
                )
                .properties(title=title)
            )

        fig_col1, fig_col2, fig_col3 = st.columns(3)
        with fig_col1:
            if len(rev_numeric):
                chart = _altair_revenue_bars(rev_numeric, "Revenue distribution")
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No revenue data for selected filters.")
        with fig_col2:
            if len(medicare_numeric):
                chart = _altair_revenue_bars(medicare_numeric, "Medicare revenue distribution")
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No Medicare revenue data for selected filters.")
        with fig_col3:
            if len(medicaid_numeric):
                chart = _altair_revenue_bars(medicaid_numeric, "Medicaid revenue distribution")
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No Medicaid revenue data for selected filters.")

        st.subheader("Pareto charts")
        pa1, pa2, pa3 = st.columns(3)
        with pa1:
            if len(rev_numeric):
                chart = make_pareto_altair(
                    pd.to_numeric(filtered[rev_col], errors="coerce").dropna(),
                    "Revenue",
                    "Revenue Pareto",
                    value_scale=1e6,
                    value_suffix="$M",
                )
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No revenue data for selected filters.")
        with pa2:
            if len(medicare_numeric):
                chart = make_pareto_altair(
                    pd.to_numeric(filtered[MEDICARE_REV_COL], errors="coerce").dropna(),
                    "Medicare revenue",
                    "Medicare revenue Pareto",
                    value_scale=1e6,
                    value_suffix="$M",
                )
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No Medicare revenue data for selected filters.")
        with pa3:
            if len(medicaid_numeric):
                chart = make_pareto_altair(
                    pd.to_numeric(filtered[MEDICAID_REV_COL], errors="coerce").dropna(),
                    "Medicaid revenue",
                    "Medicaid revenue Pareto",
                    value_scale=1e6,
                    value_suffix="$M",
                )
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No Medicaid revenue data for selected filters.")

        st.subheader("Home health revenue by state (from providers)")
        map_df = state_revenue_from_providers(providers_raw, year=year, states=states if states else None)
        map_df = map_df.rename(columns={"State Code": "state", "Gross Patient Revenues Total": "revenue"})
        if map_df["revenue"].sum() > 0:
            map_df = map_df.copy()
            map_df["id"] = map_df["state"].map(STATE_TO_FIPS)
            states_topo = alt.topo_feature(US_10M_URL, "states")
            choro = (
                alt.Chart(states_topo)
                .mark_geoshape()
                .encode(
                    color=alt.Color("revenue:Q", scale=alt.Scale(scheme="blues"), title="Revenue"),
                    tooltip=[alt.Tooltip("state:N", title="State"), alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f")],
                )
                .transform_lookup(lookup="id", from_=alt.LookupData(map_df, "id", ["revenue", "state"]))
                .project(type="albersUsa")
                .properties(width=700, height=500, title="State-level home health revenue (providers_annual)")
            )
            st.altair_chart(choro, use_container_width=True)
        else:
            st.info("No provider revenue data for selected year/filters.")

        st.subheader("Medicare revenue by provider location")
        _centroid_cache_key = ZIP_LAT_LON_PATH.stat().st_mtime if ZIP_LAT_LON_PATH.exists() else 0.0
        zip_centroids = load_zip_centroids(_cache_key=_centroid_cache_key)
        if zip_centroids is not None:
            prov = providers_raw[providers_raw["year"] == year].copy()
            if states:
                prov = prov[prov["State Code"].isin(states)]
            prov["zip5"] = prov["Zip Code"].astype(str).str.strip().str.replace("-", "").str[:5]
            prov = prov[prov["zip5"].str.match(r"^\d{5}$", na=False)]
            prov[MEDICARE_REV_COL] = pd.to_numeric(prov[MEDICARE_REV_COL], errors="coerce").fillna(0)
            prov = prov[prov[MEDICARE_REV_COL] > 0]
            prov_map = prov.merge(zip_centroids, left_on="zip5", right_on="zip", how="inner")
            if not prov_map.empty:
                prov_map = prov_map.copy()
                prov_map["medicare_rev"] = pd.to_numeric(prov_map[MEDICARE_REV_COL], errors="coerce").fillna(0)
                # Size scale: area proportional to revenue; use sqrt for radius
                prov_map["size"] = np.sqrt(prov_map["medicare_rev"].clip(lower=1))
                chart_df = prov_map[["lat", "lon", "size", "medicare_rev", "HHA Name", "zip5"]].copy()
                chart_df["Medicare revenue"] = chart_df["medicare_rev"]  # for tooltip label
                circle_chart = (
                    alt.Chart(chart_df)
                    .mark_circle(opacity=0.6, stroke="white", strokeWidth=0.5)
                    .encode(
                        longitude="lon:Q",
                        latitude="lat:Q",
                        size=alt.Size("size:Q", scale=alt.Scale(range=[20, 1200]), title="Medicare revenue"),
                        color=alt.Color("medicare_rev:Q", scale=alt.Scale(scheme="blues"), title="Medicare revenue"),
                        tooltip=[
                            alt.Tooltip("HHA Name:N", title="Provider"),
                            alt.Tooltip("zip5:N", title="ZIP"),
                            alt.Tooltip("Medicare revenue:Q", format="$,.0f", title="Medicare revenue"),
                        ],
                    )
                    .project(type="albersUsa")
                    .properties(width=700, height=500, title="Revenue by provider CCN ZIP")
                )
                st.altair_chart(circle_chart, use_container_width=True)
            else:
                st.info("No providers with Medicare revenue for selected year/filters.")
        else:
            st.info(
                "Map requires zip centroids. Add **zip_lat_lon.csv** (columns: zip, lat, lon) to the project, "
                "or ensure the app can download the Census 2020 ZCTA gazetteer."
            )


if __name__ == "__main__":
    main()
