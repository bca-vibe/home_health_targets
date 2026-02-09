# Data Dictionary: HHA Transformed Tables

This document describes the two derived tables built from CMS Home Health Agency (HHA) cost report data: **providers_annual** and **operators_annual**. Source data are the annual cost report CSVs (2020–2023) in the `20XX/CostReporthha_Final_XX.csv` files.

---

## Table: providers_annual

**Purpose:** One row per provider (unique CCN) per reporting year, with identity, location, ownership, volume, cost, revenue, and balance-sheet fields. Includes an **operator_id** that links multiple CCNs to the same operator (multi-site).

**Row count:** One row per (Provider CCN, year). Same CCN in multiple years appears in multiple rows.

| Column | Type | Description |
|--------|------|-------------|
| year | integer | Reporting year (2020, 2021, 2022, or 2023). Derived from the source filename. |
| operator_id | integer | Identifier for the operator (legal/trade name group). Same value for all CCNs that share the same normalized HHA Name; blank if HHA Name was empty. Used to link to **operators_annual** and to identify multi-site operators. |
| HHA Name | text | Home Health Agency name as reported on the cost report (legal or trade name). |
| rpt_rec_num | text | Cost report record number from CMS. |
| Provider CCN | text | CMS Certification Number; unique per certified agency/location. |
| Street Address | text | Street address of the agency as reported. |
| City | text | City. |
| State Code | text | Two-letter state code. |
| Zip Code | text | ZIP code. |
| Type of Control | text | CMS ownership/control type code (e.g., 1–2 voluntary nonprofit, 3–6 proprietary, 7–13 governmental). See CMS HHA cost report instructions for full code list. |
| Fiscal Year Begin Date | text | Start date of the cost report fiscal period. |
| Fiscal Year End Date | text | End date of the cost report fiscal period. |
| HHA-based Hospice Provider CCN | text | CCN of affiliated hospice provider, if any. |
| Total, Medicare Title XVIII Visits | numeric | Total visits under Medicare (Title XVIII) for the report period. |
| Total, Medicaid Title XIX Visits | numeric | Total visits under Medicaid (Title XIX). |
| Total, Other Visits | numeric | Total visits from other payers (e.g., commercial, private pay). |
| Total, Total Visits | numeric | Total visits across all payers. |
| Total Episodes-Total Visits | numeric | Total visits in episode-based count (Medicare-oriented). |
| Total Episodes-Total Charges | numeric | Total charges associated with episodes. |
| Total Cost | numeric | Total operating cost for the period. |
| Total HHA Medicare Program Visits | numeric | Visits under the HHA Medicare program. |
| Total HHA Medicare Program Cost | numeric | Cost allocated to the HHA Medicare program. |
| Gross Patient Revenues Title XVIII Medicare | numeric | Gross patient revenue from Medicare. |
| Gross Patient Revenues Title XIX Medicaid | numeric | Gross patient revenue from Medicaid. |
| Gross Patient Revenues Other | numeric | Gross patient revenue from other payers. |
| Gross Patient Revenues Total | numeric | Total gross patient revenue (all payers). |
| Less: Allowances and discounts on patients' accounts Title XVIII Medicare | numeric | Allowances and discounts applied to Medicare revenue. |
| Less: Allowances and discounts on patients' accounts Title XIX Medicaid | numeric | Allowances and discounts applied to Medicaid revenue. |
| Less: Allowances and discounts on patients' accounts Other | numeric | Allowances and discounts applied to other revenue. |
| Less: Allowances and discounts on patients' accounts Total | numeric | Total allowances and discounts. |
| Net Patient Revenues (line 1 minus line 2) XVIII Medicare | numeric | Net patient revenue from Medicare after allowances/discounts. |
| Net Patient Revenues (line 1 minus line 2) XIX Medicaid | numeric | Net patient revenue from Medicaid after allowances/discounts. |
| Net Patient Revenues (line 1 minus line 2) Other | numeric | Net patient revenue from other payers after allowances/discounts. |
| Net Patient Revenues (line 1 minus line 2) Total | numeric | Total net patient revenue. |
| Less Total Operating Expenses (sum of lines 4 through 16) | numeric | Total operating expenses per cost report worksheet. |
| Net Income from service to patients (line 3 minus line 17) | numeric | Income from patient care (net revenue minus operating expenses). |
| Total Other Income (sum of lines 19 through 31) | numeric | Other income per cost report. |
| Net Income or Loss for the period (line 18 plus line 32) | numeric | Net income or loss for the reporting period. |
| Total PPS Payment - full episodes/periods without outliers | numeric | Medicare PPS payment for full episodes without outliers. |
| Total PPS Payment - full episodes/periods with outliers | numeric | Medicare PPS payment for full episodes with outliers. |
| Total PPS Payment - LUPA episodes/periods | numeric | Medicare PPS payment for LUPA (low-utilization) episodes. |
| Total PPS Payment - PEP episodes/periods | numeric | Medicare PPS payment for PEP (partial episode) periods. |
| Total PPS Outlier Payment - full episodes/periods with outliers | numeric | Outlier payment for full episodes. |
| Total PPS Outlier Payment - PEP episodes/periods | numeric | Outlier payment for PEP episodes. |
| Allowable Bad Debts | numeric | Allowable bad debt amount. |
| Adjusted Reimbursable Bad Debts | numeric | Adjusted reimbursable bad debt amount. |
| Total Current Assets | numeric | Total current assets from balance sheet. |
| Total Fixed Assets | numeric | Total fixed assets. |
| Total Assets | numeric | Total assets. |
| Total Current Liabilities | numeric | Total current liabilities. |
| Total Long Term Liabilities | numeric | Total long-term liabilities. |
| Total Liabilities | numeric | Total liabilities. |
| Fund Balance | numeric | Fund balance (equity). |
| Total Liabilities and Fund Balances | numeric | Total liabilities and fund balances. |
| Total Hospice Days Title XVIII Medicare | numeric | Hospice days under Medicare, if agency reports hospice. |
| Total Hospice Days Title XIX Medicaid | numeric | Hospice days under Medicaid. |
| Total Hospice Days Title Other | numeric | Hospice days under other payers. |
| Total Hospice Days Total | numeric | Total hospice days. |
| Total Hospice Expenses | numeric | Total hospice expenses, if applicable. |

**Notes:**

- Empty or missing values in the source appear as blank in the CSV.
- **operator_id** is assigned by normalizing **HHA Name** (uppercase, single spaces); identical normalized names share one operator_id across all years.

---

## Table: operators_annual

**Purpose:** One row per operator per year, with financial and volume metrics **aggregated across all CCNs** that belong to that operator (same normalized HHA Name). Use for operator-level analysis and multi-site rollups.

**Row count:** One row per (operator_id, year). Only operators with a non-blank normalized HHA Name are included.

| Column | Type | Description |
|--------|------|-------------|
| year | integer | Reporting year (2020–2023). |
| operator_id | integer | Operator identifier; matches **operator_id** in **providers_annual**. |
| operator_name | text | Canonical name for the operator in this year (most frequently occurring HHA Name among the operator’s CCNs). |
| n_ccns | integer | Number of distinct Provider CCNs (sites) for this operator in this year. |
| n_states | integer | Number of distinct states in which the operator had at least one CCN. |
| state_codes | text | Pipe-separated list of state codes (e.g., `FL\|GA\|TX`) where the operator had CCNs. |
| Gross Patient Revenues Title XVIII Medicare | numeric | **Sum** of Medicare gross patient revenue across all CCNs. |
| Gross Patient Revenues Title XIX Medicaid | numeric | **Sum** of Medicaid gross patient revenue across all CCNs. |
| Gross Patient Revenues Other | numeric | **Sum** of other gross patient revenue across all CCNs. |
| Gross Patient Revenues Total | numeric | **Sum** of total gross patient revenue across all CCNs. |
| Net Patient Revenues (line 1 minus line 2) XVIII Medicare | numeric | **Sum** of Medicare net patient revenue across all CCNs. |
| Net Patient Revenues (line 1 minus line 2) XIX Medicaid | numeric | **Sum** of Medicaid net patient revenue across all CCNs. |
| Net Patient Revenues (line 1 minus line 2) Other | numeric | **Sum** of other net patient revenue across all CCNs. |
| Net Patient Revenues (line 1 minus line 2) Total | numeric | **Sum** of total net patient revenue across all CCNs. |
| Total Cost | numeric | **Sum** of total cost across all CCNs. |
| Total HHA Medicare Program Cost | numeric | **Sum** of HHA Medicare program cost across all CCNs. |
| Total, Total Visits | numeric | **Sum** of total visits across all CCNs. |
| Total Episodes-Total Visits | numeric | **Sum** of episode visits across all CCNs. |
| Total Episodes-Total Charges | numeric | **Sum** of episode charges across all CCNs. |
| Less Total Operating Expenses (sum of lines 4 through 16) | numeric | **Sum** of total operating expenses across all CCNs. |
| Net Income from service to patients (line 3 minus line 17) | numeric | **Sum** of income from patient care across all CCNs. |
| Net Income or Loss for the period (line 18 plus line 32) | numeric | **Sum** of net income/loss across all CCNs. |
| Total Assets | numeric | **Sum** of total assets across all CCNs. |
| Total Liabilities | numeric | **Sum** of total liabilities across all CCNs. |
| Fund Balance | numeric | **Sum** of fund balance across all CCNs. |
| Total PPS Payment - full episodes/periods without outliers | numeric | **Sum** of PPS payment (full, no outliers) across all CCNs. |
| Total PPS Payment - full episodes/periods with outliers | numeric | **Sum** of PPS payment (full, with outliers) across all CCNs. |
| Total PPS Payment - LUPA episodes/periods | numeric | **Sum** of LUPA PPS payment across all CCNs. |
| Total PPS Payment - PEP episodes/periods | numeric | **Sum** of PEP PPS payment across all CCNs. |
| Total Hospice Days Total | numeric | **Sum** of total hospice days across all CCNs. |
| Total Hospice Expenses | numeric | **Sum** of total hospice expenses across all CCNs. |

**Notes:**

- All numeric financial and volume fields are **summed** across the operator’s CCNs for that year.
- **n_ccns** = 1 indicates a single-site operator; **n_ccns** > 1 indicates a multi-site operator.
- **operator_name** can vary slightly by year if reporting names differ across CCNs; the value stored is the mode (most common) HHA Name for that operator in that year.

---

## Source and build

- **Source:** CMS HHA cost reports, `20XX/CostReporthha_Final_XX.csv` (2020–2023).
- **Build script:** `transform_to_tables.py`. Run from the project root with:  
  `python3 transform_to_tables.py`  
  to regenerate **providers_annual.csv** and **operators_annual.csv**.
