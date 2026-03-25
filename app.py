# Mini Project 2 - Information Visualization Dashboard, by Rohan Bhalla.
# In the project AI assistance of Cursor was used to help with the code

#Imports for the project
import pathlib
import os
import numpy as np
import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

# file path to be set for loading the data
BASE_PATH = pathlib.Path(__file__).parent
DATA_PATH = BASE_PATH / "data" / "arabica_data_cleaned.csv"

# Loading the data from the csv
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

    # Harvest year extract first 4 digit year from the full string
    raw_year = df["Harvest.Year"].astype(str).str.extract(r"(\d{4})", expand=False)
    df["HarvestYearStart"] = pd.to_numeric(raw_year, errors="coerce")
    # Keep only plausible harvest years so timeline is not distorted. Removing years processed incorrectly
    df.loc[(df["HarvestYearStart"] < 1990) | (df["HarvestYearStart"] > 2030), "HarvestYearStart"] = pd.NA

    # Certification flag is a simple boolean being assigned and is shown as a KPI in the dashboard
    df["HasCertification"] = df["Certification.Body"].astype(str).str.strip().ne("").astype(int)

    # Quality band is a simple calculated field that is used to group the data into bands of quality. This is shown as a legend in the dashboard
    def quality_band(score: float) -> str:
        if pd.isna(score):
            return "Unknown"
        if score >= 87:
            return "87+"
        if score >= 84:
            return "84–86.99"
        if score >= 80:
            return "80–83.99"
        return "Below 80"

    df["QualityBand"] = df["Total.Cup.Points"].apply(quality_band)

    # Altitude columns ensure numeric and fix known data-entry outliers. This is used to create the scatter plot in the dashboard
    for col in ("altitude_low_meters", "altitude_high_meters", "altitude_mean_meters"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = pd.NA
    if "altitude_mean_meters" not in df.columns or df["altitude_mean_meters"].isna().all():
        alt = df["Altitude"].astype(str).str.extractall(r"(\d+\.?\d*)")[0].groupby(level=0).mean()
        df["altitude_mean_meters"] = pd.to_numeric(alt, errors="coerce")

    # Fix 3 known outliers that stretch the scatter. Original data set had unit errors that have to be filtered out like this
    for col in ("altitude_low_meters", "altitude_high_meters", "altitude_mean_meters"):
        if col not in df.columns:
            continue
        m = df[col]
        mask_100x = (m >= 100_000) & (m < 1_000_000)  
        mask_10x = (m >= 10_000) & (m < 100_000)     
        mask_high = (m > 5_000) & (m < 10_000)
        df.loc[mask_100x, col] = df.loc[mask_100x, col] / 100
        df.loc[mask_10x, col] = df.loc[mask_10x, col] / 10
        df.loc[mask_high, col] = pd.NA

    return df

# data frame being set for all the data
df_all = load_data()


# Custom categorical colors for processing methods based on user feedback
PROCESSING_COLORS = {
    "Washed / Wet": "#52BCA3",          # Teal
    "Natural / Dry": "#F29E38",         # Orange
    "Pulped natural / honey": "#5D64D3",# Indigo
    "Semi-washed / Semi-pulped": "#D96599", # Pink
    "Other": "#8D8DF1",                 # Light Purple
}

# Distinct marker shapes for chart 1 to pass the black and white test as well (as seen in class)
PROCESSING_SYMBOLS = {
    "Washed / Wet": "circle",
    "Natural / Dry": "square",
    "Pulped natural / honey": "diamond",
    "Semi-washed / Semi-pulped": "triangle-up",
    "Other": "hexagon",
}

# Anchor legend flush to the plotting area (less gap than default)
LEGEND_NEAR_CHART = dict(
    xref="paper",
    yref="paper",
    x=1,
    y=1,
    xanchor="left",
    yanchor="top",
)

# Slightly larger typography inside Plotly figures based on user feedback
CHART_FONT_SIZE = 17
CHART_AXIS_TITLE_FONT_SIZE = 17
CHART_TICK_FONT_SIZE = 17
CHART_LEGEND_TITLE_FONT_SIZE = 17
CHART_LEGEND_ITEM_FONT_SIZE = 17
CHART_ANNOTATION_FONT_SIZE = 17
CHART_POLAR_TICK_FONT_SIZE = 17
CHART_BAR_TEXT_FONT_SIZE = 17
CHART_FIGURE_TITLE_FONT_SIZE = 17
CHART_COLORBAR_TICK_FONT_SIZE = 17
CHART_COLORBAR_TITLE_FONT_SIZE = 17


# Chart 1: Altitude vs Coffee Quality (use drop down to select from the y axis options listed below)
Y_METRIC_OPTIONS = {
    "Total.Cup.Points": "Total Cup Points",
    "Aroma": "Aroma",
    "Flavor": "Flavor",
    "Aftertaste": "Aftertaste",
    "Acidity": "Acidity",
    "Body": "Body",
    "Balance": "Balance",
    "Sweetness": "Sweetness",
    "Uniformity": "Uniformity",
    "Clean.Cup": "Clean Cup",
    "Cupper.Points": "Cupper Points",
}


external_stylesheets = [dbc.themes.BOOTSTRAP]
app: Dash = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server


def make_layout() -> html.Div:
    # KPI hover text (tool tips for the KPIs to explain to the user what they mean)
    kpi_tooltip_avg_score = (
        "Average Total Cup Points for samples in your current selection. "
        "This is the Coffee Quality Institute's overall cupping score (sensory quality); "
        "higher values mean better perceived quality. Updates when you filter by year, map, scatter, or processing."
    )
    kpi_tooltip_avg_moisture = (
        "Average green (unroasted) coffee moisture content (%). "
        "Moisture is tracked for storage and processing; typical export coffee is often roughly 9–12%. "
        "Reflects only the samples matching your active filters."
    )
    kpi_tooltip_total_certs = (
        "Number of samples in the current selection that list a certification body. "
        "Each row counts once; samples with no certification body are excluded from this total."
    )
    kpi_tooltip_total_samples = (
        "How many cupping records are included after your filters (year range, country, scatter selection, processing method). "
        "All charts and the other KPIs use this same filtered subset."
    )

    min_year = int(df_all["HarvestYearStart"].min())
    max_year = int(df_all["HarvestYearStart"].max())

    return dbc.Container(
        [
            dcc.Store(id="filter-clear-store", data=0),
            html.H2(
                "Arabica Coffee Quality Dashboard (Made Using Plotly Dash)",
                className="mt-3 mb-1 fw-bold",
                style={"fontSize": "2.15rem"},
            ),
            html.P(
                "Interactive exploration of Coffee Quality Institute cupping data: "
                "quality correlations, regional patterns, sensory profiles, and processing impact. "
                "Select a country on the map, drag to select points on the scatter, or set the year range to filter all views.",
                className="text-muted mb-2 fs-5",
            ),
            html.Div(
                [
                    html.Button(
                        "Clear filters (map, scatter, processing)",
                        id="clear-filters-btn",
                        className="btn btn-outline-secondary",
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Avg Total Score", className="fw-semibold fs-5 py-2"),
                                    dbc.CardBody(html.H3(id="kpi-avg-quality", className="mb-0 fs-2")),
                                ],
                                id="kpi-card-avg-quality",
                                className="h-100",
                                style={"cursor": "help"},
                            ),
                            dbc.Tooltip(
                                kpi_tooltip_avg_score,
                                target="kpi-card-avg-quality",
                                placement="bottom",
                            ),
                        ]
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Avg Moisture", className="fw-semibold fs-5 py-2"),
                                    dbc.CardBody(html.H3(id="kpi-avg-moisture", className="mb-0 fs-2")),
                                ],
                                id="kpi-card-avg-moisture",
                                className="h-100",
                                style={"cursor": "help"},
                            ),
                            dbc.Tooltip(
                                kpi_tooltip_avg_moisture,
                                target="kpi-card-avg-moisture",
                                placement="bottom",
                            ),
                        ]
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Total Certifications", className="fw-semibold fs-5 py-2"),
                                    dbc.CardBody(html.H3(id="kpi-total-certifications", className="mb-0 fs-2")),
                                ],
                                id="kpi-card-total-certifications",
                                className="h-100",
                                style={"cursor": "help"},
                            ),
                            dbc.Tooltip(
                                kpi_tooltip_total_certs,
                                target="kpi-card-total-certifications",
                                placement="bottom",
                            ),
                        ]
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                [
                                    dbc.CardHeader("Total samples", className="fw-semibold fs-5 py-2"),
                                    dbc.CardBody(html.H3(id="kpi-total-samples", className="mb-0 fs-2")),
                                ],
                                id="kpi-card-total-samples",
                                className="h-100",
                                style={"cursor": "help"},
                            ),
                            dbc.Tooltip(
                                kpi_tooltip_total_samples,
                                target="kpi-card-total-samples",
                                placement="bottom",
                            ),
                        ]
                    ),
                ],
                className="mb-5",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H5(
                                            "Chart 1: How altitude relates to cup quality",
                                            className="chart-section-title mb-2 fw-semibold",
                                        ),
                                        html.Div(
                                            [
                                                html.Span(
                                                    "Y-axis (how altitude affects):",
                                                    className="me-2 fs-6",
                                                ),
                                                dcc.Dropdown(
                                                    id="y-metric-dropdown",
                                                    options=[
                                                        {"label": label, "value": key}
                                                        for key, label in Y_METRIC_OPTIONS.items()
                                                    ],
                                                    value="Total.Cup.Points",
                                                    clearable=False,
                                                    style={"width": "240px", "fontSize": "1.05rem"},
                                                ),
                                            ],
                                            className="d-flex align-items-center mb-2",
                                        ),
                                        html.P(
                                            "Processing method is shown by both color and marker shape.",
                                            className="text-muted d-block mb-2 small",
                                            style={"fontSize": "1rem"},
                                        ),
                                    ],
                                ),
                                dcc.Graph(
                                    id="scatter-graph",
                                    config={"displayModeBar": True},
                                    style={"height": "440px"},
                                ),
                            ],
                            className="chart-section-block h-100",
                        ),
                        xs=12,
                        md=6,
                        lg=6,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5(
                                    "Chart 2: Average quality by country",
                                    className="chart-section-title mb-2 fw-semibold",
                                ),
                                dcc.Graph(
                                    id="map-graph",
                                    config={"displayModeBar": False},
                                    style={"height": "440px"},
                                ),
                            ],
                            className="chart-section-block h-100",
                        ),
                        xs=12,
                        md=6,
                        lg=6,
                    ),
                ],
                className="dashboard-chart-grid-row g-4 mb-4 align-items-stretch",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5(
                                    "Chart 3: Flavor profile by country or species",
                                    className="chart-section-title mb-2 fw-semibold",
                                ),
                                html.Div(
                                    [
                                        html.Span("Group by:", className="me-2 fs-6"),
                                        dcc.Dropdown(
                                            id="sensory-group-dropdown",
                                            options=[
                                                {"label": "Species", "value": "Species"},
                                                {"label": "Country (region)", "value": "Country.of.Origin"},
                                            ],
                                            value="Country.of.Origin",
                                            clearable=False,
                                            style={"width": "180px", "fontSize": "1.05rem"},
                                        ),
                                        html.Span("View:", className="ms-3 me-2 fs-6"),
                                        dcc.Dropdown(
                                            id="sensory-view-dropdown",
                                            options=[
                                                {"label": "Radar", "value": "radar"},
                                                {"label": "Bar (compare values)", "value": "bar"},
                                            ],
                                            value="radar",
                                            clearable=False,
                                            style={"width": "200px", "fontSize": "1.05rem"},
                                        ),
                                    ],
                                    className="d-flex align-items-center mb-2 flex-wrap",
                                ),
                                dcc.Graph(
                                    id="sensory-graph",
                                    config={"displayModeBar": True},
                                    style={"height": "440px"},
                                ),
                            ],
                            className="chart-section-block h-100",
                        ),
                        xs=12,
                        md=6,
                        lg=6,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5(
                                    "Chart 4: Does processing affect scores?",
                                    className="chart-section-title mb-2 fw-semibold",
                                ),
                                dcc.Graph(
                                    id="processing-graph",
                                    config={"displayModeBar": True},
                                    style={"height": "440px"},
                                ),
                            ],
                            className="chart-section-block h-100",
                        ),
                        xs=12,
                        md=6,
                        lg=6,
                    ),
                ],
                className="dashboard-chart-grid-row g-4 mb-4 align-items-stretch",
            ),
            html.Div(
                [
                    html.H5(
                        "Chart 5: How average quality changes by harvest year",
                        className="chart-section-title mb-2 fw-semibold",
                    ),
                    dcc.Graph(id="timeline-graph", config={"displayModeBar": True}),
                    dcc.RangeSlider(
                        id="year-range-slider",
                        min=min_year,
                        max=max_year,
                        value=[min_year, max_year],
                        marks={int(y): str(int(y)) for y in sorted(df_all["HarvestYearStart"].dropna().unique())},
                        step=1,
                        allowCross=False,
                        className="mt-3 mb-0",
                    ),
                ],
                className="chart-section-block mb-4",
            ),
            html.P(
                "Coordinated views: (1) Click a country on the map to filter all charts. "
                "(2) Use the year range slider to filter by harvest year. "
                "(3) Lasso or box-select points on the scatter to filter all views. "
                "(4) Click a bar in the processing chart to show only that processing method in every chart. "
                "Use \"Clear filters\" to reset map, scatter, and processing selection.",
                className="text-muted small mb-0",
                style={"fontSize": "1rem"},
            ),
        ],
        fluid=True,
        className="pb-3",
        style={"fontSize": "1.075rem"},
    )


app.layout = make_layout


def filtered_data(year_range, country_click, scatter_selection, processing_click=None, clear_override=False):
    #Apply coordinated filters: year range, then map, scatter selection, then processing method.
    #When clear_override is True, ignore map, scatter, and processing click (used after clear filters).
    df = df_all.copy()

    # Year range filter (always applied)
    if year_range and len(year_range) >= 2:
        start_year, end_year = year_range[0], year_range[1]
        df = df[df["HarvestYearStart"].between(start_year, end_year, inclusive="both")]

    if not clear_override:
        # Map country filter (selecting data in one view filters all others)
        if country_click and "points" in country_click and country_click["points"]:
            country = country_click["points"][0].get("location")
            if country:
                df = df[df["Country.of.Origin"] == country]

        # Scatter selection / linked brushing (selecting points filters all views)
        if scatter_selection and "points" in scatter_selection:
            selected_indices = [p["pointIndex"] for p in scatter_selection["points"]]
            if selected_indices:
                df = df.iloc[selected_indices]

        # Chart 4 bar click: filter to selected processing method only
        if processing_click and "points" in processing_click and processing_click["points"]:
            method = processing_click["points"][0].get("x")
            if method is not None and isinstance(method, str):
                df = df[df["Processing.Method"] == method]

    return df

# Callback function to update the dashboard when the user interacts with the dashboard.
@app.callback(
    [
        Output("kpi-avg-quality", "children"),
        Output("kpi-avg-moisture", "children"),
        Output("kpi-total-certifications", "children"),
        Output("kpi-total-samples", "children"),
        Output("scatter-graph", "figure"),
        Output("map-graph", "figure"),
        Output("sensory-graph", "figure"),
        Output("processing-graph", "figure"),
        Output("timeline-graph", "figure"),
        Output("filter-clear-store", "data"),
    ],
    [
        Input("y-metric-dropdown", "value"),
        Input("year-range-slider", "value"),
        Input("map-graph", "clickData"),
        Input("scatter-graph", "selectedData"),
        Input("processing-graph", "clickData"),
        Input("clear-filters-btn", "n_clicks"),
        Input("sensory-group-dropdown", "value"),
        Input("sensory-view-dropdown", "value"),
    ],
    [State("filter-clear-store", "data")],
)

# This function is used to update the dashboard when the user interacts with the dashboard. It is called when the user changes the year range, country, scatter selection, processing method, or clears the filters.
def update_dashboard(
    y_metric, year_range, country_click, scatter_selection, processing_click, clear_clicks, sensory_group, sensory_view, clear_store
):
    # When user clicks Clear filters, ignore map, scatter, and processing selection for this run
    clear_override = False
    new_clear_store = clear_store or 0
    if clear_clicks and clear_clicks > (clear_store or 0):
        clear_override = True
        new_clear_store = clear_clicks

    df = filtered_data(year_range, country_click, scatter_selection, processing_click=processing_click, clear_override=clear_override)

    # KPIs are calculated and displayed in the dashboard. They are used to display the average quality, average moisture, total certifications, and total samples.
    avg_quality = df["Total.Cup.Points"].mean()
    avg_moisture = df["Moisture"].mean()
    total_cert = df["HasCertification"].sum()

    kpi_quality_text = f"{avg_quality:.2f}" if pd.notna(avg_quality) else "—"
    kpi_moisture_text = f"{avg_moisture:.2f}" if pd.notna(avg_moisture) else "—"
    kpi_cert_text = f"{int(total_cert)}" if pd.notna(total_cert) else "0"
    kpi_samples_text = str(len(df))

    # Chart 1: Scatter with reduced overplotting and visible trend (information visualization principles)
    y_label = Y_METRIC_OPTIONS.get(y_metric, y_metric)
    scatter_fig = px.scatter(
        df,
        x="altitude_mean_meters",
        y=y_metric,
        color="Processing.Method",
        symbol="Processing.Method",
        size="Number.of.Bags",
        hover_data=["Country.of.Origin", "Region", "Farm.Name", "Variety"],
        labels={"altitude_mean_meters": "Altitude (mean m)", y_metric: y_label},
        template="plotly_white",
        size_max=14,  # Cap size so large bags don't dominate and obscure density
        color_discrete_map=PROCESSING_COLORS,
        symbol_map=PROCESSING_SYMBOLS,
    )
    # Lower opacity so overlapping points show density; slightly thicker outline helps read shape
    scatter_fig.update_traces(marker={"opacity": 0.42, "line": {"width": 0.75, "color": "white"}})
    scatter_fig.update_layout(
        margin=dict(l=10, r=100, t=50, b=40),
        dragmode="lasso",
        title=None,
        font=dict(size=CHART_FONT_SIZE),
        xaxis=dict(range=[0, 3500]),
        legend={
            "title": dict(text="Processing method (color + shape)", font=dict(size=CHART_LEGEND_TITLE_FONT_SIZE)),
            "font": dict(size=CHART_LEGEND_ITEM_FONT_SIZE),
            "itemwidth": 36,
            "tracegroupgap": 12,
            "itemsizing": "constant",
            "bgcolor": "rgba(255,255,255,0.92)",
            "bordercolor": "rgba(0,0,0,0.15)",
            "borderwidth": 1,
            **LEGEND_NEAR_CHART,
        },
    )
    scatter_fig.update_xaxes(
        tickfont=dict(size=CHART_TICK_FONT_SIZE),
        title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
    )
    scatter_fig.update_yaxes(
        tickfont=dict(size=CHART_TICK_FONT_SIZE),
        title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
    )

    corr_r = None
    if not df.empty and y_metric in df.columns:
        numeric_df = df[["altitude_mean_meters", y_metric]].dropna()
        if len(numeric_df) >= 2:
            x_vals = numeric_df["altitude_mean_meters"]
            y_vals = numeric_df[y_metric]
            r = y_vals.corr(x_vals)
            if pd.notna(r):
                corr_r = r
            # Linear trend line only when x has variation (avoid divide-by-zero)
            x_var = pd.Series(x_vals).var()
            if pd.notna(x_var) and x_var > 0:
                coeffs = pd.Series(y_vals).cov(x_vals) / x_var
                intercept = y_vals.mean() - coeffs * x_vals.mean()
                x_line = pd.Series(sorted(x_vals.unique()))
                y_line = intercept + coeffs * x_line
                scatter_fig.add_trace(
                    go.Scatter(
                        x=x_line,
                        y=y_line,
                        mode="lines",
                        line=dict(color="black", width=2, dash="dash"),
                        name="Linear trend",
                        hoverinfo="skip",
                    )
                )
            # Binned mean (aggregation): reduces noise and makes trend visible
            bin_edges = list(range(0, 3501, 500))
            numeric_df = numeric_df.copy()
            numeric_df["alt_bin"] = pd.cut(numeric_df["altitude_mean_meters"], bins=bin_edges, include_lowest=True)
            binned = numeric_df.groupby("alt_bin", observed=True)[y_metric].agg(["mean", "count"]).reset_index()
            binned = binned[binned["alt_bin"].notna() & (binned["count"] >= 3)]
            binned["alt_mid"] = binned["alt_bin"].apply(lambda c: (c.left + c.right) / 2)
            if len(binned) >= 2:
                scatter_fig.add_trace(
                    go.Scatter(
                        x=binned["alt_mid"],
                        y=binned["mean"],
                        mode="lines+markers",
                        line=dict(color="darkorange", width=3),
                        marker=dict(size=10, symbol="diamond"),
                        name="Binned mean (500 m)",
                        hoverinfo="y+name",
                    )
                )
    # Takeaway annotation (make the finding explicit)
    if corr_r is not None:
        strength = "Weak" if abs(corr_r) < 0.3 else ("Moderate" if abs(corr_r) < 0.6 else "Strong")
        direction = "positive" if corr_r > 0 else "negative"
        scatter_fig.add_annotation(
            text=f"r = {corr_r:.3f} — {strength} {direction}",
            xref="paper", yref="paper", x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=CHART_ANNOTATION_FONT_SIZE),
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.8)",
        )

    # Map (choropleth by country)
    map_df = df.dropna(subset=["Country.of.Origin"])
    map_agg = (
        map_df.groupby("Country.of.Origin", as_index=False)
        .agg(avg_score=("Total.Cup.Points", "mean"), count=("Total.Cup.Points", "size"))
        .sort_values("avg_score", ascending=False)
    )
    map_fig = px.choropleth(
        map_agg,
        locations="Country.of.Origin",
        locationmode="country names",
        color="avg_score",
        color_continuous_scale="YlGn",
        labels={"avg_score": "Avg Total Score"},
        hover_data={"count": True},
        template="plotly_white",
    )
    map_fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        font=dict(size=CHART_FONT_SIZE),
        coloraxis_colorbar=dict(
            title=dict(text="Score", font=dict(size=CHART_COLORBAR_TITLE_FONT_SIZE)),
            tickfont=dict(size=CHART_COLORBAR_TICK_FONT_SIZE),
        ),
    )

    # Sensory profiles by region and species (research Q2)
    sensory_measures = ["Aroma", "Flavor", "Aftertaste", "Acidity", "Body", "Balance", "Sweetness"]
    group_col = sensory_group if sensory_group else "Country.of.Origin"
    sensory_df = (
        df.dropna(subset=[group_col] + sensory_measures)
        .groupby(group_col)[sensory_measures]
        .mean()
        .reset_index()
    )
    # If grouping by country, keep top 10 by number of rows in filtered data to avoid clutter
    if group_col == "Country.of.Origin" and len(sensory_df) > 10:
        counts = df.dropna(subset=[group_col]).groupby(group_col).size().sort_values(ascending=False).head(10)
        top = counts.index.tolist()
        sensory_df = sensory_df[sensory_df[group_col].isin(top)]

    sensory_view = sensory_view or "radar"
    sensory_legend_title = "Country (region)" if group_col == "Country.of.Origin" else "Species"
    # Match Chart 1 legend styling for readability (font, swatch width, frame)
    sensory_legend = {
        "title": dict(text=sensory_legend_title, font=dict(size=CHART_LEGEND_TITLE_FONT_SIZE)),
        "font": dict(size=CHART_LEGEND_ITEM_FONT_SIZE),
        "itemwidth": 36,
        "tracegroupgap": 12,
        "itemsizing": "constant",
        "bgcolor": "rgba(255,255,255,0.92)",
        "bordercolor": "rgba(0,0,0,0.15)",
        "borderwidth": 1,
        **LEGEND_NEAR_CHART,
    }

    if sensory_view == "bar":
        # Bar view: easier to read exact values and compare attributes across groups
        long_df = sensory_df.melt(
            id_vars=[group_col], value_vars=sensory_measures,
            var_name="Attribute", value_name="Score",
        )
        sensory_fig = px.bar(
            long_df,
            x="Score",
            y="Attribute",
            color=group_col,
            orientation="h",
            barmode="group",
            template="plotly_white",
            labels={"Score": "Mean score"},
        )
        sensory_fig.update_layout(
            margin=dict(l=80, r=100, t=10, b=40),
            font=dict(size=CHART_FONT_SIZE),
            legend=sensory_legend,
            xaxis=dict(range=[7, 10], dtick=0.5),
            yaxis=dict(categoryorder="array", categoryarray=list(reversed(sensory_measures))),
        )
        sensory_fig.update_xaxes(
            tickfont=dict(size=CHART_TICK_FONT_SIZE),
            title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
        )
        sensory_fig.update_yaxes(
            tickfont=dict(size=CHART_TICK_FONT_SIZE),
            title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
        )
    else:
        # Radar: data-driven radial range so the polygon uses the full circle
        if not sensory_df.empty:
            r_min = sensory_df[sensory_measures].min().min()
            r_max = sensory_df[sensory_measures].max().max()
            pad = 0.25
            radial_low = max(0, float(r_min) - pad)
            radial_high = min(10, float(r_max) + pad)
            radial_range = [radial_low, radial_high]
        else:
            radial_range = [7, 10]

        sensory_fig = go.Figure()
        for _, row in sensory_df.iterrows():
            values = [row[m] for m in sensory_measures]
            sensory_fig.add_trace(
                go.Scatterpolar(
                    r=values + values[:1],
                    theta=sensory_measures + sensory_measures[:1],
                    mode="lines+markers",
                    name=str(row[group_col]),
                    line=dict(width=2),
                    marker=dict(size=6),
                )
            )
        sensory_fig.update_layout(
            font=dict(size=CHART_FONT_SIZE),
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=radial_range,
                    tickfont=dict(size=CHART_POLAR_TICK_FONT_SIZE),
                ),
                angularaxis=dict(tickfont=dict(size=CHART_TICK_FONT_SIZE)),
            ),
            template="plotly_white",
            showlegend=True,
            legend=sensory_legend,
            margin=dict(l=30, r=100, t=10, b=10),
        )

    # Chart 4: Processing method vs quality (research Q3) – bar chart for clear comparison
    proc_df = df.dropna(subset=["Processing.Method", "Total.Cup.Points"])
    if not proc_df.empty:
        proc_stats = (
            proc_df.groupby("Processing.Method")["Total.Cup.Points"]
            .agg(["mean", "std", "count"])
        )
        # Safe SE/CI: only when count > 1 (avoid divide-by-zero and NaN std for single point)
        n = proc_stats["count"]
        se = pd.Series(0.0, index=proc_stats.index)
        valid = n > 1
        if valid.any():
            se = se.astype(float)
            se.loc[valid] = (proc_stats["std"].fillna(0) / np.sqrt(n)).loc[valid]
        proc_stats = proc_stats.assign(se=se, ci95=1.96 * se)
        # Sort by mean descending so "higher quality" is visually to the left (easier to scan)
        proc_stats = proc_stats.sort_values("mean", ascending=False)
        overall_mean = proc_df["Total.Cup.Points"].mean()
        processing_fig = go.Figure(
            data=[
                go.Bar(
                    x=proc_stats.index.tolist(),
                    y=proc_stats["mean"],
                    error_y=dict(type="data", array=proc_stats["ci95"], visible=True),
                    marker_color=[PROCESSING_COLORS.get(m, "#CCCCCC") for m in proc_stats.index.tolist()],
                    text=[f"n={int(n)}" for n in proc_stats["count"]],
                    textposition="outside",
                    textfont=dict(size=CHART_BAR_TEXT_FONT_SIZE),
                )
            ],
            layout=dict(
                template="plotly_white",
                font=dict(size=CHART_FONT_SIZE),
                xaxis_title="Processing method",
                yaxis_title="Mean total cup points",
                yaxis=dict(range=[75, 90], dtick=2),
                margin=dict(l=50, r=20, t=50, b=100),
                showlegend=False,
            ),
        )
        processing_fig.update_xaxes(
            tickfont=dict(size=CHART_TICK_FONT_SIZE),
            title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
        )
        processing_fig.update_yaxes(
            tickfont=dict(size=CHART_TICK_FONT_SIZE),
            title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
        )
        # Reference line: overall mean (context for above/below average)
        processing_fig.add_hline(
            y=overall_mean,
            line_dash="dash",
            line_color="gray",
            annotation_text="Overall mean",
            annotation_position="right",
            annotation_font_size=CHART_ANNOTATION_FONT_SIZE,
        )
        processing_fig.update_layout(
            title=dict(
                text="Mean quality by processing method (error bars: 95% CI)",
                font=dict(size=CHART_FIGURE_TITLE_FONT_SIZE),
                x=0.5,
                xanchor="center",
            ),
            xaxis_tickangle=-25,
        )
    else:
        processing_fig = go.Figure().add_annotation(
            text="No data",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=CHART_FIGURE_TITLE_FONT_SIZE),
        )
        processing_fig.update_layout(
            template="plotly_white",
            font=dict(size=CHART_FONT_SIZE),
            margin=dict(l=40, r=10, t=10, b=80),
        )

    # Timeline
    timeline_df = (
        df.dropna(subset=["HarvestYearStart"])
        .groupby("HarvestYearStart", as_index=False)["Total.Cup.Points"]
        .mean()
        .rename(columns={"Total.Cup.Points": "AvgScore"})
    )
    timeline_fig = px.line(
        timeline_df,
        x="HarvestYearStart",
        y="AvgScore",
        markers=True,
        template="plotly_white",
        labels={"HarvestYearStart": "Harvest Year", "AvgScore": "Avg Total Score"},
    )
    timeline_fig.update_layout(
        margin=dict(l=40, r=10, t=10, b=40),
        font=dict(size=CHART_FONT_SIZE),
    )
    timeline_fig.update_xaxes(
        tickfont=dict(size=CHART_TICK_FONT_SIZE),
        title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
    )
    timeline_fig.update_yaxes(
        tickfont=dict(size=CHART_TICK_FONT_SIZE),
        title_font=dict(size=CHART_AXIS_TITLE_FONT_SIZE),
    )

    return (
        kpi_quality_text,
        f"{kpi_moisture_text} %",
        kpi_cert_text,
        kpi_samples_text,
        scatter_fig,
        map_fig,
        sensory_fig,
        processing_fig,
        timeline_fig,
        new_clear_store,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    app.run_server(host="0.0.0.0", port=port, debug=True)

