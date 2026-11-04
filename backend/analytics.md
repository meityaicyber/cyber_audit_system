# Security Analytics System Documentation

This document provides a detailed overview of the Architecture, Database Schema, Backend Services, API Endpoints, and Frontend UI components of the Security Analytics system.

---

## 1. Architectural Overview

The Security Analytics dashboard processes and visualizes vulnerability data extracted from audited security reports. The diagram below illustrates the end-to-end data flow:

```mermaid
graph TD
    subgraph Database Layer [Database Layer (PostgreSQL)]
        A[(reports_data)] 
        B[(vulnerabilities)]
    end

    subgraph Service Layer [Backend Service app/services/analytics_service.py]
        C[get_summary]
        D[get_severity_distribution]
        E[get_status_distribution]
        F[get_cvss_distribution]
        G[get_category_breakdown]
        H[get_trend]
        I[get_top_cwe/top_cve/get_affected_assets]
        J[get_new_vs_repeat]
        K[get_recent_vulns]
    end

    subgraph API Router [REST Router app/routers/analytics.py]
        L[/api/analytics/* Endpoints]
    end

    subgraph Frontend Dashboard [React Frontend AnalyticsDashboardPage.jsx]
        M[Promise.allSettled Fetcher]
        N[Recharts Components]
        O[KPI Stat Cards]
        P[Recent Vulns Table]
    end

    %% Connections
    A & B --> C & D & E & F & G & H & I & J & K
    C & D & E & F & G & H & I & J & K --> L
    L --> M
    M --> N & O & P
```

---

## 2. Database Models & Schema

The analytics are populated from the PostgreSQL database using two primary models defined in [report.py](file:///c:/Main%20Project/Module/backend/backend/app/models/report.py):

### Vulnerability Table (`vulnerabilities`)
Each vulnerability contains structured fields that feed directly into analytics aggregations:
* **`vuln_id`** (UUID, Primary Key): Unique identifier for each finding.
* **`report_id`** (UUID, Foreign Key): Links the vulnerability to its parent report.
* **`severity`** (Enum: `SeverityLevel`): Can be `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFORMATIONAL`.
* **`status`** (Enum: `VulnStatus`): Represents current remediation status (`OPEN`, `CLOSED`, `ACCEPTED`, `RISK_ACCEPTED`, `IN_PROGRESS`).
* **`cvss_score`** (Numeric 3,1): Numeric score from `0.0` to `10.0`.
* **`category`** (Text): Categorization of the security issue.
* **`new_or_repeat`** (Text): Track if a vulnerability is a first-time finding or a repeating/re-discovered one.
* **`cwe_ids`** (ARRAY(Text)): List of Common Weakness Enumeration identifiers.
* **`cve_ids`** (ARRAY(Text)): List of Common Vulnerabilities and Exposures identifiers.
* **`affected_assets`** (ARRAY(Text)): List of assets affected by the vulnerability.

### Reports Data Table (`reports_data`)
* **`report_id`** (UUID, Primary Key / Foreign Key)
* **`report_date`** (Date): Used for historical trending.
* **`data`** (JSONB): Raw report results.

---

## 3. Backend Service Layer

The business and aggregation logic is defined in [analytics_service.py](file:///c:/Main%20Project/Module/backend/backend/app/services/analytics_service.py). It uses SQL-level groupings and functions to optimize query execution.

### Core Functions & Aggregations

#### 1. High-Level Metrics Summary
* **Function**: `get_summary(db)`
* **Description**: Returns overall metric totals (Total, Open, and Closed vulnerability counts), average CVSS score, severity counts, and total reports analyzed.
* **SQL Query Pattern**: Uses standard SQLAlchemy `func.count(Vulnerability.vuln_id)` and `func.avg(Vulnerability.cvss_score)`.

#### 2. Categorized Distributions
* **Functions**: `get_severity_distribution(db)` & `get_status_distribution(db)`
* **Description**: Aggregates vulnerability counts grouped by severity or status.
* **Logic**: Standardizes response mappings to ensure zero-count fields (e.g. `INFORMATIONAL` or `ACCEPTED` status) still return `0` instead of being omitted.

#### 3. Histogram and Array Unnesting
* **CVSS Score Distribution (`get_cvss_distribution`)**: Computes counts across specific ranges (e.g. `0.0` to `1.0`, `1.0` to `2.0`, etc.) to build a histogram.
* **Array-based Analytics (`get_top_cwe`, `get_top_cve`, `get_affected_assets`)**: 
  Since CWEs, CVEs, and assets are stored in PostgreSQL arrays, standard string groupings cannot be used. The service executes raw SQL queries utilizing PostgreSQL's **`unnest()`** function:
  ```sql
  SELECT cwe, COUNT(*) AS count
  FROM vulnerabilities, unnest(cwe_ids) AS cwe
  WHERE cwe_ids IS NOT NULL
  GROUP BY cwe
  ORDER BY count DESC
  LIMIT 10;
  ```

#### 4. Historical Trends & Growth Analysis
* **Trend Timeline (`get_trend`)**:
  Performs an SQL query joining `vulnerabilities` and `reports_data` on `report_id` to aggregate data grouped by monthly periods (`date_trunc('month', rd.report_date)`) over the preceding 12-month period:
  ```sql
  SELECT
      to_char(date_trunc('month', rd.report_date), 'YYYY-MM') AS month,
      COUNT(v.vuln_id) AS count
  FROM vulnerabilities v
  JOIN reports_data rd ON v.report_id = rd.report_id
  WHERE rd.report_date >= (CURRENT_DATE - INTERVAL '12 months')
    AND rd.report_date IS NOT NULL
  GROUP BY date_trunc('month', rd.report_date)
  ORDER BY date_trunc('month', rd.report_date);
  ```

---

## 4. API Layer

The endpoints are exposed under `/api/analytics` in [analytics.py](file:///c:/Main%20Project/Module/backend/backend/app/routers/analytics.py).

| Endpoint | Method | Response Schema | Description |
| :--- | :---: | :--- | :--- |
| `/summary` | `GET` | `AnalyticsSummary` | Overall statistics dashboard numbers. |
| `/severity-distribution` | `GET` | `SeverityDistribution` | Counts divided by Critical, High, Medium, Low, etc. |
| `/status-distribution` | `GET` | `StatusDistribution` | Counts divided by Open, Closed, Accepted, In Progress. |
| `/cvss-distribution` | `GET` | `CvssDistribution` | CVSS frequency list categorized by score. |
| `/category-breakdown` | `GET` | `CategoryBreakdown` | Top 15 vulnerability classes/types. |
| `/trend` | `GET` | `VulnTrend` | Monthly historical counts (last 12 months). |
| `/top-cwe` | `GET` | `TopCwe` | Top 10 CWE weaknesses. |
| `/top-cve` | `GET` | `TopCve` | Top 10 CVE IDs. |
| `/affected-assets` | `GET` | `AffectedAssets` | Top 15 most vulnerability-prone assets. |
| `/new-vs-repeat` | `GET` | `NewVsRepeat` | Delineation between new and repeat findings. |
| `/recent-vulns` | `GET` | `RecentVulns` | Details for the latest 10 vulnerabilities. |

* **Dependency Guards**: Each endpoint utilizes standard FastAPI dependencies:
  * `current_user: User = Depends(get_current_user)` (ensures valid session token).
  * `db: AsyncSession = Depends(get_db)` (handles transaction/session lifetimes).

---

## 5. Frontend Dashboard UI

The client-side view is managed inside [AnalyticsDashboardPage.jsx](file:///c:/Main%20Project/Module/backend/frontend/src/pages/AnalyticsDashboardPage.jsx) using React, Material-UI (MUI) components, and Recharts.

### Frontend Flow & Lifecycle

1. **State Initialization**: Declares local state variables corresponding to each metrics API response block (e.g. `summary`, `severityDist`, etc.) along with a `loading` indicator.
2. **Concurrent Request Fetching (`fetchAll`)**:
   Fetches all eleven endpoints concurrently in a single async block using **`Promise.allSettled()`**:
   ```javascript
   const [summaryRes, sevRes, ...] = await Promise.allSettled([
     api.get('/api/analytics/summary'),
     api.get('/api/analytics/severity-distribution'),
     ...
   ]);
   ```
   This prevents a single failed request from breaking the entire page; succeeded responses will populate, while failed responses gracefully fall back to empty states.
3. **Skeleton Loading State**:
   While requests are active, the component displays loading skeletal shapes mapping out the dashboard structure to improve perceived performance.

### Interactive Components

* **KPI Summary Cards (`KpiCard`)**:
  Features animated counters (`AnimatedNumber`) utilizing a Cubic Easing equation inside a React `requestAnimationFrame` loop, producing smooth numeric counting animations on load.
* **Charts & Tooltips**:
  * **Donut Charts**: Severity and status divisions are visualized using inner and outer radius parameters on a `PieChart`. Curated colors reflect threat levels (e.g. `#FF1744` for Critical).
  * **Trend Timeline**: Configured with a gradient area chart (`AreaChart`) fading from light blue to transparent.
  * **Top Categories / Assets**: Vertical bar layout charts where labels auto-truncate to prevent label overlaps.
  * **Custom Tooltip (`GlassTooltip`)**: Uses a translucent backdrop glassmorphism effect (`backdropFilter: 'blur(16px)'`) displaying hovered values.
* **Recent Table List**:
  Renders a table of the latest 10 vulnerabilities highlighting active Severity chips and status indicators, linking into details.
