"""
HHA Dashboard: Operators table and Dashboard tab with filters.
Uses providers_annual.csv and operators_annual.csv.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
OPERATORS_PATH = PROJECT_DIR / "operators_annual.csv"
PROVIDERS_PATH = PROJECT_DIR / "providers_annual.csv"

# Type of Control: 3,4,5,6 = For-profit; 1,2 = Non-profit; else Other
FOR_PROFIT_CODES = {"3", "4", "5", "6"}
NONPROFIT_CODES = {"1", "2"}

# All US state abbreviations for choropleth (include DC)
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]


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
    """Map CMS Type of Control code to For-profit / Non-profit / Other (government/other)."""
    code = _normalize_toc_code(toc)
    if not code:
        return "Other"
    if code in FOR_PROFIT_CODES:
        return "For-profit"
    if code in NONPROFIT_CODES:
        return "Non-profit"
    return "Other"


@st.cache_data
def build_enriched_operators(
    operators: pd.DataFrame,
    providers: pd.DataFrame,
) -> pd.DataFrame:
    """Add revenue_growth_pct, net_income_margin_pct, ownership."""
    rev_col = "Gross Patient Revenues Total"
    ni_col = "Net Income or Loss for the period (line 18 plus line 32)"

    # Prior-year revenue
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

    # Net income margin
    op[ni_col] = pd.to_numeric(op[ni_col], errors="coerce")
    op["net_income_margin_pct"] = None
    rev_pos = op[rev_col].notna() & (op[rev_col] > 0)
    op.loc[rev_pos, "net_income_margin_pct"] = (
        op.loc[rev_pos, ni_col] / op.loc[rev_pos, rev_col] * 100
    )

    # Ownership from providers: mode of Type of Control per (operator_id, year)
    # Normalize codes (e.g. 5.0 -> "5") so mapping to For-profit/Non-profit works
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


def main():
    st.set_page_config(page_title="HHA Dashboard", layout="wide")
    st.title("Home Health Agency Dashboard")

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

    ownership_options = ["For-profit", "Non-profit", "Other"]
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
            rev_col,
            ni_col,
            "net_income_margin_pct",
            "revenue_growth_pct",
            "ownership",
        ]
        table_df = table_df[display_cols].copy()
        table_df = table_df.rename(columns={
            "state_codes": "States",
            "cities": "Cities",
            rev_col: "Total revenue",
            ni_col: "Net income",
            "net_income_margin_pct": "Net income margin (%)",
            "revenue_growth_pct": "Revenue growth (%)",
            "ownership": "Type of control",
        })
        table_df["States"] = table_df["States"].str.replace("|", ", ", regex=False)
        st.dataframe(table_df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Summary metrics")
        n_op = len(filtered)
        total_rev = pd.to_numeric(filtered[rev_col], errors="coerce").sum()
        total_medicare = pd.to_numeric(filtered["Gross Patient Revenues Title XVIII Medicare"], errors="coerce").sum()
        total_medicaid = pd.to_numeric(filtered["Gross Patient Revenues Title XIX Medicaid"], errors="coerce").sum()
        margin_series = filtered["net_income_margin_pct"].dropna()
        avg_margin = margin_series.mean() if len(margin_series) else None

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Operators", f"{n_op:,}")
        c2.metric("Total revenue", format_currency(total_rev))
        c3.metric("Total Medicare revenue", format_currency(total_medicare))
        c4.metric("Total Medicaid revenue", format_currency(total_medicaid))
        c5.metric("Avg net income margin (%)", f"{avg_margin:.1f}%" if avg_margin is not None else "—")

        st.subheader("Distributions")
        rev_numeric = pd.to_numeric(filtered[rev_col], errors="coerce").dropna()
        rev_numeric = rev_numeric[rev_numeric > 0]
        medicare_numeric = pd.to_numeric(filtered["Gross Patient Revenues Title XVIII Medicare"], errors="coerce").dropna()
        medicare_numeric = medicare_numeric[medicare_numeric > 0]
        medicaid_numeric = pd.to_numeric(filtered["Gross Patient Revenues Title XIX Medicaid"], errors="coerce").dropna()
        medicaid_numeric = medicaid_numeric[medicaid_numeric > 0]
        margin_numeric = filtered["net_income_margin_pct"].dropna()

        fig_col1, fig_col2 = st.columns(2)
        with fig_col1:
            if len(rev_numeric):
                fig = px.histogram(x=rev_numeric / 1e6, nbins=50, labels={"x": "Revenue ($M)"}, title="Revenue distribution")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No revenue data for selected filters.")
        with fig_col2:
            if len(medicare_numeric):
                fig = px.histogram(x=medicare_numeric / 1e6, nbins=50, labels={"x": "Medicare revenue ($M)"}, title="Medicare revenue distribution")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No Medicare revenue data for selected filters.")

        fig_col3, fig_col4 = st.columns(2)
        with fig_col3:
            if len(medicaid_numeric):
                fig = px.histogram(x=medicaid_numeric / 1e6, nbins=50, labels={"x": "Medicaid revenue ($M)"}, title="Medicaid revenue distribution")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No Medicaid revenue data for selected filters.")
        with fig_col4:
            if len(margin_numeric):
                fig = px.histogram(x=margin_numeric, nbins=50, labels={"x": "Net income margin (%)"}, title="Net income margin distribution")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No net income margin data for selected filters.")

        st.subheader("Home health revenue by state (from providers)")
        map_df = state_revenue_from_providers(providers_raw, year=year, states=states if states else None)
        map_df = map_df.rename(columns={"State Code": "state", "Gross Patient Revenues Total": "revenue"})
        if map_df["revenue"].sum() > 0:
            fig = px.choropleth(
                map_df,
                locations="state",
                locationmode="USA-states",
                color="revenue",
                scope="usa",
                color_continuous_scale="Blues",
                title="State-level home health revenue (providers_annual)",
            )
            fig.update_traces(hovertemplate="%{location}<br>Revenue: $%{z:,.0f}<extra></extra>")
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No provider revenue data for selected year/filters.")


if __name__ == "__main__":
    main()
