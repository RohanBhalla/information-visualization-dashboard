## Tableau Public build guide (Arabica coffee)

This guide implements the dashboard plan in the attached `tableau_coffee_dashboard_33ce3bbc.plan.md` **without editing that plan file**.

### Goal (what you’ll end up with)

- **An interactive multi-view Tableau Public dashboard** with:
  - **≥3 coordinated views** connected via **cross-filtering/linked highlighting**
  - **≥4 dimensions** encoded using distinct visual channels (position/color/size/faceting)
  - A layout that uses **Gestalt grouping** (containers + alignment + whitespace)
  - Clear support for the 3 research questions in `project-requirements.md`

### Files you already have

- **Arabica dataset**: `data/arabica_data_cleaned.csv`
- **Requirements**: `project-requirements.md`

---

## 1) Connect data + set roles/types (Data Source tab)

### Connect

1. Open **Tableau Public**.
2. Connect → **Text file** → select `data/arabica_data_cleaned.csv`.

### Fix data types (recommended)

In the Data Source grid, confirm/adjust these:

- **Measures (Number/Decimal)**:
  - `Total.Cup.Points`, `Aroma`, `Flavor`, `Aftertaste`, `Acidity`, `Body`, `Balance`, `Sweetness`
  - `Moisture`, `Number.of.Bags`, `Category.One.Defects`, `Category.Two.Defects`, `Quakers`
  - `altitude_low_meters`, `altitude_high_meters`, `altitude_mean_meters`
- **Dimensions (String)**:
  - `Species`, `Country.of.Origin`, `Region`, `Processing.Method`, `Variety`, `Color`
  - `Farm.Name`, `Owner`, `Producer`, `Company`
- **Dates**:
  - Keep `Grading.Date` as a String if parsing is inconsistent; you’ll use `Harvest.Year` for the timeline.

### Geographic role (for the map)

Right-click `Country.of.Origin` → **Geographic Role** → **Country/Region**.

---

## 2) Create required calculated fields + parameter

Create these in the Data pane (right-click → **Create Calculated Field**).

### 2.1 `HarvestYearStart` (Integer year for timeline)

```text
INT(LEFT(STR([Harvest.Year]), 4))
```

### 2.2 `HasCertification` (0/1 for KPI)

```text
IF ISNULL([Certification.Body]) OR TRIM([Certification.Body]) = '' THEN 0 ELSE 1 END
```

### 2.3 `QualityBand` (legend consistency)

```text
IF [Total.Cup.Points] >= 87 THEN '87+'
ELSEIF [Total.Cup.Points] >= 84 THEN '84–86.99'
ELSEIF [Total.Cup.Points] >= 80 THEN '80–83.99'
ELSE 'Below 80'
END
```

### 2.4 (Recommended) Parameter + calc for “correlation explorer”

#### Create parameter `X_Metric`

- Data type: **String**
- Allowable values (List):
  - `Altitude (mean m)`
  - `Acidity`
  - `Body`
  - `Sweetness`
  - `Aroma`
  - `Flavor`
  - `Moisture`

#### Create calculated field `X_Value`

```text
CASE [X_Metric]
WHEN 'Altitude (mean m)' THEN [altitude_mean_meters]
WHEN 'Acidity' THEN [Acidity]
WHEN 'Body' THEN [Body]
WHEN 'Sweetness' THEN [Sweetness]
WHEN 'Aroma' THEN [Aroma]
WHEN 'Flavor' THEN [Flavor]
WHEN 'Moisture' THEN [Moisture]
END
```

#### Create calculated field `X_Label` (for axis title)

```text
[X_Metric]
```

Show the parameter control later on the dashboard.

---

## 3) Build worksheets (suggested names match the plan)

You’ll create **6 worksheet views** + **3 KPI tiles**.

### 3.1 KPI tiles (3 sheets)

Create each as a Text table (Marks = Text), then format as a “tile”.

#### Sheet: `KPI - Avg Quality`

- Put `AVG([Total.Cup.Points])` on **Text**
- Format:
  - Font size large (e.g., 22–32), bold
  - Set **Number Format** to 2 decimals
  - Hide title if you’ll use dashboard text labels

#### Sheet: `KPI - Avg Moisture`

- Put `AVG([Moisture])` on **Text**
- Format to percent or 2 decimals (whichever reads better for your data; sample uses percent-like)

#### Sheet: `KPI - Total Certifications`

- Put `SUM([HasCertification])` on **Text**
- Number format: integer

Tip: remove gridlines/dividers and keep padding consistent so these read as a single KPI strip.

---

### 3.2 Scatter: `Chart 1 - Correlation Explorer`

Purpose: answer **“What attributes most strongly associate with overall coffee quality?”**

- Columns: `X_Value`
- Rows: `Total.Cup.Points`
- Marks: **Circle**
  - **Color**: `Processing.Method` (or `QualityBand` if you want quality-centric coloring)
  - **Size**: `Number.of.Bags`
  - **Detail**: `Country.of.Origin`, `Region`, `Farm.Name` (use what’s populated)
- Analytics:
  - Add **Trend Line** (Linear)
  - Optional: add reference line at `AVG(Total.Cup.Points)`
- Tooltip (recommended fields):
  - `Farm.Name`, `Country.of.Origin`, `Region`
  - `Processing.Method`, `Variety`, `Species`
  - `Total.Cup.Points`
  - The chosen `X_Label` and `X_Value`

Axis title: use `X_Label` in the sheet title/subtitle (Tableau can’t dynamically rename an axis title reliably; a sheet subtitle is the easiest).

---

### 3.3 Map: `Chart 2 - Quality by Country (Map)`

Purpose: support geography-driven filtering and answer distribution questions.

- Double-click `Country.of.Origin` to generate the map
- Marks: **Filled Map**
  - **Color**: `AVG([Total.Cup.Points])` (sequential palette)
  - **Detail**: `Country.of.Origin`
- Tooltip:
  - Avg quality
  - `COUNT([Country.of.Origin])` (or `Number of Records`)

---

### 3.4 Sensory profile: `Chart 3 - Sensory Profile (Species Compare)`

Purpose: answer **“How do sensory profiles vary by region and species?”**

This uses a “profile line” across sensory measures (Tableau-friendly and stable on Public).

- Columns: `Measure Names`
- Rows: `Measure Values`
- Marks: **Line**
- In Measure Values, keep only:
  - `Aroma`, `Flavor`, `Aftertaste`, `Acidity`, `Body`, `Balance`, `Sweetness`
- Color: `Species`
- Optional:
  - Add `Country.of.Origin` to Filters (will be driven by a dashboard action)
  - Add `Region` to Detail or Filters (if populated)

If lines overlap too much, change to small multiples:

- Rows: `Species`
- Keep the same `Measure Names` → `Measure Values` line inside each row.

---

### 3.5 Processing impact: `Chart 4 - Processing vs Quality (Box Plot)`

Purpose: answer **“Does processing method affect coffee quality scores?”**

Option A (preferred): Box plot

- Columns: `Processing.Method`
- Rows: `Total.Cup.Points`
- Show Me → **Box-and-Whisker Plot**
- Color: `Processing.Method` (or keep neutral and use `QualityBand` as color if you want)
- Sort processing methods by `AVG(Total.Cup.Points)` for readability

Option B (if box plot is messy): Bar chart

- Columns: `Processing.Method`
- Rows: `AVG(Total.Cup.Points)`
- Add error bars if desired

---

### 3.6 Timeline: `Chart 5 - Harvest Trend (Range Filter)`

Purpose: global time filter + context.

- Columns: `HarvestYearStart` (Discrete or Continuous; choose what looks best)
- Rows: `AVG([Total.Cup.Points])`
- Marks: Area or Line
- Put `HarvestYearStart` on Filters:
  - Filter type: **Range of values**
  - Show filter (you can show it on the dashboard as a slider)

If `HarvestYearStart` has nulls, filter out Null.

---

## 4) Assemble the dashboard (layout + Gestalt grouping)

Create a new Dashboard: `Coffee Quality Dashboard (Arabica)`

### Layout (container-based)

- Use **Vertical container** as the root.
- Add **Horizontal container** for KPIs (top strip):
  - `KPI - Avg Quality` | `KPI - Avg Moisture` | `KPI - Total Certifications`
- Add **Horizontal container** for the main row:
  - Left: `Chart 1 - Correlation Explorer` (make this the largest view)
  - Right: `Chart 2 - Quality by Country (Map)`
- Add **Horizontal container** for the lower row:
  - `Chart 3 - Sensory Profile (Species Compare)`
  - `Chart 4 - Processing vs Quality (Box Plot)`
- Add `Chart 5 - Harvest Trend (Range Filter)` at the bottom, full width.

### Visual hierarchy + polish

- Keep a single dashboard title at top (or in a header area).
- Use consistent fonts and sizes.
- Align edges; keep consistent padding/whitespace.
- Keep legends consolidated (prefer 1–2 max visible at once).
- Reduce clutter:
  - Hide worksheet titles and use dashboard text headers instead (more consistent).
  - Remove gridlines on KPI tiles and the box plot (keep only subtle axis ticks).
  - Keep tooltips to ~6–10 lines; prioritize fields that explain the mark.
- Color + accessibility:
  - Prefer a color-blind-safe palette for categorical color (Processing/Species).
  - For the map’s sequential palette, ensure sufficient contrast between low/high.

### Controls

Show these controls on the dashboard:

- Parameter control: `X_Metric` (so users can switch the correlation driver)
- Harvest year filter slider from the Timeline sheet (or add as a global filter card)

Suggested placement:

- Put `X_Metric` near the scatter (top-left of the main row).
- Put the year slider directly above the timeline (bottom), spanning full width.

---

## 5) Add cross-filtering + linked highlighting (Dashboard → Actions)

You must satisfy the requirement: selecting data in one view highlights/filters corresponding data in others.

### 5.1 Map → Filter everything else

Dashboard → Actions → Add Action → **Filter**

- Source sheet: `Chart 2 - Quality by Country (Map)`
- Run action on: **Select**
- Target sheets: scatter, sensory, processing, KPIs, timeline
- Clearing selection: **Show all values**
- Filter fields: **Selected Fields** → `Country.of.Origin` → `Country.of.Origin`

### 5.2 Timeline → Filter everything else

Dashboard → Actions → Add Action → **Filter**

- Source sheet: `Chart 5 - Harvest Trend (Range Filter)` (or the filter card)
- Run action on: **Select**
- Target sheets: all other sheets
- Clearing selection: **Show all values**
- Filter fields: **Selected Fields** → `HarvestYearStart` → `HarvestYearStart`

### 5.3 Scatter → Highlight related marks

Dashboard → Actions → Add Action → **Highlight**

- Source sheet: `Chart 1 - Correlation Explorer`
- Target sheets: map + sensory + processing
- Fields to match:
  - Start with `Country.of.Origin` (most reliable)
  - Optionally add `Processing.Method` (if you want stronger “method” coupling)
- Run action on: **Select**
- Clearing selection: **Show all values**

### 5.4 Reset affordance

Tableau Public users can use the toolbar **Revert** button.
Add a small text note near the top-right: “Tip: use Revert to reset filters.”

---

## 6) Requirement checklist (verify before publishing)

### Interactivity (≥3 coordinated views)

You should be able to:

- Select a **country** on the map → scatter/sensory/processing/KPIs update.
- Adjust **harvest year range** → all charts update.
- Select points in the **scatter** → related items highlight in other views.

### ≥4 dimensions with distinct channels

Example mapping that satisfies the requirement:

- **Position**: scatter \(X_Value vs Total.Cup.Points\)
- **Color**: `Processing.Method` (or `QualityBand`)
- **Size**: `Number.of.Bags` (scatter)
- **Facet/Group**: `Species` (sensory profile color or small multiples)
  Additional dimensions appear via geography (map) and time (timeline).

### Research questions

- **Correlation with quality**: use the scatter + `X_Metric` parameter + trend line.
- **Sensory by region/species**: map selection filters sensory profile; compare `Species`.
- **Processing method effect**: box plot (or bars) shows distribution/mean differences.

---

## 7) Publish on Tableau Public

1. Server → **Tableau Public** → Save to Tableau Public.
2. Title the workbook clearly (e.g., “Coffee Quality Dashboard (Arabica)”).
3. After publishing, open the published view and confirm:
   - Actions work (map selection, highlight, timeline filter)
   - Tooltips are readable and not cluttered
   - Legends/controls are discoverable
   - Default state tells a story (no empty views; sensible default `X_Metric` like “Altitude (mean m)”)

### Final validation (quick, explicit)

- **≥3 coordinated views**:
  - Selecting a country on the map filters **Scatter + Sensory + Processing + KPIs**.
  - Harvest year range filters **all** views.
  - Scatter selection highlights related marks in **Map/Sensory/Processing**.
- **≥4 dimensions / channels** (example you can cite in your write-up):
  - `Total.Cup.Points` → **Position (Y)** on scatter
  - `X_Metric` / chosen `X_Value` → **Position (X)** on scatter
  - `Processing.Method` (or `QualityBand`) → **Color**
  - `Number.of.Bags` → **Size**
  - `Species` → **Color or Facet** (sensory profile)
- **Gestalt layout**:
  - KPI strip grouped by enclosure (container) and alignment
  - Main row emphasizes scatter (primary) + map (secondary) by size and proximity
- **Performance**:
  - If the map is slow, reduce mark density elsewhere (e.g., aggregate scatter by `Country.of.Origin` temporarily) or switch to extract when publishing.

---

## 8) Usability testing (quick script you can reuse)

Ask 2–3 peers to do these tasks (record time + confusion points):

- Task A: “Which attribute seems most correlated with quality? Show me evidence.”
- Task B: “Pick a country and describe how its sensory profile differs by species.”
- Task C: “Does washed vs natural show a difference in quality distribution?”

Iterate once (rename controls, adjust legends, reduce tooltip noise, improve contrast).
