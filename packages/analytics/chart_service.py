import logging
from typing import Any

_log = logging.getLogger(__name__)


class ChartService:
    """Generate chart images from data. Uses Plotly if available, else simple SVG."""

    def generate_line_chart(
        self,
        title: str,
        x_values: list,
        y_values: list,
        x_label: str = "",
        y_label: str = "",
        format: str = "svg",
    ) -> bytes:
        try:
            return self._plotly_line(title, x_values, y_values, x_label, y_label, format)
        except ImportError:
            _log.info("Plotly not available — generating SVG sparkline")
            return self._svg_sparkline(title, y_values)

    def generate_bar_chart(
        self,
        title: str,
        labels: list[str],
        values: list[float],
        format: str = "svg",
    ) -> bytes:
        try:
            return self._plotly_bar(title, labels, values, format)
        except ImportError:
            return self._svg_bar(title, labels, values)

    def _plotly_line(self, title, x, y, xl, yl, fmt):
        import plotly.graph_objects as go

        fig = go.Figure(data=go.Scatter(x=x, y=y, mode="lines+markers"))
        fig.update_layout(
            title=title,
            xaxis_title=xl,
            yaxis_title=yl,
            template="plotly_white",
            width=800,
            height=400,
        )
        if fmt == "png":
            return fig.to_image(format="png")
        return fig.to_image(format="svg")

    def _plotly_bar(self, title, labels, values, fmt):
        import plotly.graph_objects as go

        fig = go.Figure(data=go.Bar(x=labels, y=values))
        fig.update_layout(
            title=title, template="plotly_white", width=800, height=400
        )
        if fmt == "png":
            return fig.to_image(format="png")
        return fig.to_image(format="svg")

    def _svg_sparkline(self, title: str, values: list[float]) -> bytes:
        if not values:
            return b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="10" y="50">No data</text></svg>'
        w, h = 400, 100
        mn, mx = min(values), max(values)
        rng = mx - mn if mx != mn else 1
        points = []
        for i, v in enumerate(values):
            x = 10 + (i / max(len(values) - 1, 1)) * (w - 20)
            y = h - 10 - ((v - mn) / rng) * (h - 20)
            points.append(f"{x:.1f},{y:.1f}")
        polyline = " ".join(points)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <text x="10" y="15" font-size="12" fill="#333">{title}</text>
  <polyline points="{polyline}" fill="none" stroke="#0f5cc0" stroke-width="2"/>
</svg>'''
        return svg.encode("utf-8")

    def _svg_bar(self, title: str, labels: list[str], values: list[float]) -> bytes:
        if not values:
            return b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><text x="10" y="50">No data</text></svg>'
        w, h = 400, 200
        mx = max(values) if values else 1
        bar_w = max(20, (w - 40) / len(values) - 4)
        bars = []
        for i, (label, val) in enumerate(zip(labels, values)):
            x = 20 + i * (bar_w + 4)
            bar_h = (val / mx) * (h - 50) if mx else 0
            y = h - 20 - bar_h
            bars.append(
                f'<rect x="{x:.0f}" y="{y:.0f}" width="{bar_w:.0f}" height="{bar_h:.0f}" fill="#0f5cc0"/>'
            )
            bars.append(
                f'<text x="{x + bar_w / 2:.0f}" y="{h - 5}" font-size="9" text-anchor="middle" fill="#666">{label[:8]}</text>'
            )
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <text x="10" y="15" font-size="12" fill="#333">{title}</text>
  {"".join(bars)}
</svg>'''
        return svg.encode("utf-8")
