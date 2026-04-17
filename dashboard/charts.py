from __future__ import annotations

import pandas as pd
import plotly.express as px


PALETTE = [
    "#006a6a",
    "#0d8a8a",
    "#5aa39a",
    "#d2872c",
    "#a8432a",
    "#5f6b7a",
    "#1f4d5e",
]

AXIS_LABELS = {
    "n_cases": "Case Reports",
    "delta": "Quarter-over-Quarter Change (Cases)",
    "year_q": "Reporting Quarter",
    "drugname": "Drug Name",
    "pt": "Reaction Term (MedDRA PT)",
    "outc_cod": "Outcome",
    "indi_pt": "Indication",
    "country": "Reporting Country",
    "occr_country": "Reporting Country",
    "canonical_mfr": "Manufacturer",
    "manufacturer": "Manufacturer",
    "ingredient": "Active Ingredient",
    "age_group": "Age Group",
    "rpsr_cod": "Reporter Type",
    "dose_form": "Dosage Form",
    "dose_freq": "Dose Frequency",
    "dose": "Dose",
    "route": "Administration Route",
    "sex": "Sex",
}


def _pretty_axis_label(col: str) -> str:
    if col in AXIS_LABELS:
        return AXIS_LABELS[col]
    return col.replace("_", " ").strip().title()


def _apply_professional_layout(
    fig, *, x_col: str | None = None, y_col: str | None = None
):
    fig.update_layout(
        template="plotly_white",
        title={"x": 0.01, "xanchor": "left"},
        font={
            "family": "Source Sans Pro, Segoe UI, Helvetica, Arial, sans-serif",
            "size": 13,
        },
        hoverlabel={"font_size": 12},
    )
    if x_col:
        fig.update_xaxes(
            title_text=_pretty_axis_label(x_col), tickformat=",d", showgrid=True
        )
    if y_col:
        fig.update_yaxes(title_text=_pretty_axis_label(y_col), showgrid=False)
    return fig


def empty_figure(title: str = "No data"):
    fig = px.scatter(title=title)
    fig.update_traces(marker={"opacity": 0})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def bar_horizontal(df: pd.DataFrame, x_col: str, y_col: str, title: str):
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return empty_figure(title)
    plot_df = df.sort_values(x_col, ascending=True).copy()
    n_rows = max(1, len(plot_df))
    dynamic_height = max(380, min(880, 48 + (n_rows * 32)))

    fig = px.bar(
        plot_df,
        x=x_col,
        y=y_col,
        orientation="h",
        color_discrete_sequence=[PALETTE[0]],
        title=title,
        text=x_col,
    )
    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,.0f} case reports<extra></extra>",
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=plot_df[y_col].tolist(),
        tickmode="array",
        tickvals=plot_df[y_col].tolist(),
        ticktext=[str(v) for v in plot_df[y_col].tolist()],
        automargin=True,
    )
    fig.update_layout(
        height=dynamic_height,
        margin=dict(l=10, r=20, t=40, b=10),
        showlegend=False,
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )
    return _apply_professional_layout(fig, x_col=x_col, y_col=y_col)


def line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str):
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return empty_figure(title)
    fig = px.line(df.sort_values(x_col), x=x_col, y=y_col, markers=True, title=title)
    fig.update_traces(line_color=PALETTE[0])
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
    return _apply_professional_layout(fig, x_col=x_col, y_col=y_col)


def donut(df: pd.DataFrame, names_col: str, values_col: str, title: str):
    if df.empty or names_col not in df.columns or values_col not in df.columns:
        return empty_figure(title)
    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        hole=0.55,
        color_discrete_sequence=PALETTE,
        title=title,
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_professional_layout(fig, x_col=values_col, y_col=names_col)
