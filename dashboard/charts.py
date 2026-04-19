from __future__ import annotations

import pandas as pd
import plotly.express as px


PALETTE = [
    "#2F6FED",
    "#5A92F5",
    "#85B4F8",
    "#A8C8FA",
    "#C4D9FB",
    "#DDE9FD",
    "#EEF3FE",
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
        title={"x": 0.01, "xanchor": "left", "font": {"color": "#17324D", "size": 18}},
        font={
            "family": "Manrope, Segoe UI, Helvetica, Arial, sans-serif",
            "size": 13,
            "color": "#1D2433",
        },
        hoverlabel={
            "font_size": 12,
            "bgcolor": "#FFFFFF",
            "bordercolor": "#D8DEE9",
            "font_family": "Manrope, Segoe UI, sans-serif",
        },
        plot_bgcolor="rgba(255,255,255,0)",
        paper_bgcolor="rgba(255,255,255,0)",
        margin=dict(l=24, r=36, t=56, b=24),
        legend={"font": {"color": "#17324D", "size": 12}},
    )
    if x_col:
        fig.update_xaxes(
            title_text=_pretty_axis_label(x_col),
            tickformat=",d",
            showgrid=False,
            zeroline=False,
            linecolor="rgba(126, 141, 165, 0.3)",
            tickfont={"color": "#536176"},
            title_font={"size": 12, "color": "#536176"},
            automargin=True,
        )
    if y_col:
        fig.update_yaxes(
            title_text=_pretty_axis_label(y_col),
            showgrid=False,
            zeroline=False,
            tickfont={"color": "#536176"},
            title_font={"size": 12, "color": "#536176"},
            automargin=True,
        )
    return fig


def empty_figure(title: str = "No data"):
    fig = px.scatter(title=title)
    fig.update_traces(marker={"opacity": 0})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=330)
    return fig


def _overview_drug_bar_colors(n: int) -> list[str]:
    """Top bar (largest value) is last row after ascending sort — highlight in red."""
    out: list[str] = []
    for i in range(n):
        rank_from_top = n - 1 - i
        if rank_from_top == 0:
            out.append("#2F6FED")
        elif rank_from_top <= 3:
            out.append("#5A92F5")
        else:
            out.append("#A8C8FA")
    return out


def _overview_reaction_bar_colors(n: int) -> list[str]:
    out: list[str] = []
    for i in range(n):
        rank_from_top = n - 1 - i
        if rank_from_top == 0:
            out.append("#2F6FED")
        elif rank_from_top <= 3:
            out.append("#5A92F5")
        else:
            out.append("#A8C8FA")
    return out


def bar_horizontal(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    *,
    overview_palette: str | None = None,
):
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
    if overview_palette == "drugs":
        fig.update_traces(
            marker_color=_overview_drug_bar_colors(len(plot_df)),
        )
    elif overview_palette == "reactions":
        fig.update_traces(
            marker_color=_overview_reaction_bar_colors(len(plot_df)),
        )
    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        cliponaxis=False,
        marker_line_color="rgba(255,255,255,0.7)",
        marker_line_width=1.2,
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
        showlegend=False,
        uniformtext_minsize=10,
        uniformtext_mode="show",
    )
    if plot_df[x_col].max() > 0:
        fig.update_xaxes(range=[0, float(plot_df[x_col].max()) * 1.18])
    fig = _apply_professional_layout(fig, x_col=x_col, y_col=y_col)
    if overview_palette:
        fig.update_layout(font=dict(family="Manrope, system-ui, sans-serif", size=11))
    return fig


def line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    *,
    overview_style: bool = False,
):
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return empty_figure(title)
    fig = px.line(df.sort_values(x_col), x=x_col, y=y_col, markers=True, title=title)
    if overview_style:
        fig.update_traces(
            line=dict(color="#2F6FED", width=3),
            marker=dict(size=9, color="#148A7B", line=dict(color="#FFFFFF", width=2)),
            fill="tozeroy",
            fillcolor="rgba(47, 111, 237, 0.10)",
        )
    else:
        fig.update_traces(
            line_color=PALETTE[0],
            line_width=3,
            marker=dict(size=8, color="#FFFFFF", line=dict(color=PALETTE[0], width=2)),
        )
    fig.update_layout(height=360)
    fig = _apply_professional_layout(fig, x_col=x_col, y_col=y_col)
    if overview_style:
        fig.update_layout(font=dict(family="Manrope, system-ui, sans-serif", size=11))
    return fig


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
    fig.update_layout(height=360, legend_title_text="")
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        textfont_size=12,
        textfont_color="#FFFFFF",
        marker=dict(line=dict(color="#FFFFFF", width=2)),
        hovertemplate="%{label}<br>%{value:,.0f} case reports (%{percent})<extra></extra>",
    )
    return _apply_professional_layout(fig, x_col=values_col, y_col=names_col)
