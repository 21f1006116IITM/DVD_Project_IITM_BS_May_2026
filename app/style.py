"""Shared color palette and Plotly styling helpers.

Colors follow the validated categorical / sequential / diverging / status
palette from the dataviz skill (references/palette.md) -- chosen because it
passes colorblind-safety checks (CVD Delta E, contrast) rather than by eye.
"""

# Fixed-order categorical palette (light mode). Assign by position, never
# recolor when a filter changes which series are on screen.
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

# Single-hue sequential ramp (blue), light -> dark, for magnitude encodings
# (bubble fills, ordinal delay buckets).
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab", "#0d366b"]

# Status palette -- reserved for actual state (good/neutral/bad satisfaction),
# never reused as "series 4".
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "critical": "#d03b3b",
}
SATISFACTION_COLORS = {
    "Positive (4-5)": STATUS["good"],
    "Neutral (3)": STATUS["warning"],
    "Negative (1-2)": STATUS["critical"],
}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def style_fig(fig, height=420, legend=True):
    """Apply consistent chrome to a plotly figure: font, gridlines, margins."""
    fig.update_layout(
        height=height,
        font=dict(family=FONT_FAMILY, color=INK_PRIMARY, size=13),
        plot_bgcolor=SURFACE,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=100, b=10),
        title=dict(y=0.97, yanchor="top"),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0, title_text="")
        if legend else None,
        hoverlabel=dict(bgcolor="white", font_size=12, font_family=FONT_FAMILY),
    )
    fig.update_xaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, color=INK_SECONDARY)
    fig.update_yaxes(gridcolor=GRIDLINE, zerolinecolor=BASELINE, linecolor=BASELINE, color=INK_SECONDARY)
    return fig
