from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import plotly.graph_objects as go
import plotly.express as px

# --- 追加: TOML 読み込み ---
try:
    import tomllib  # Python 3.11+
except ImportError:  # 保険
    import tomli as tomllib  # type: ignore[assignment]


QubitId = int
Coord = Tuple[float, float]
NodeProps = Mapping[str, Any]
EdgeProps = Mapping[Tuple[QubitId, QubitId], Mapping[str, Any]]


@dataclass(frozen=True)
class ColorStyle:
    colorscale: str | Sequence[str] | Sequence[Tuple[float, str]]
    colorscale_range: Tuple[float, float]
    cmin: float | None = None
    cmax: float | None = None


def load_plot_config(path: str) -> Dict[str, Any]:
    """
    描画パラメータを TOML から読み込む簡易ヘルパー。

    例: config.toml

        [plot]
        node_color_key = "T1_us"
        edge_color_key = "cx_error"
        edge_label_key = "cx_error"
        colorscale = "plasma_r"
        colorscale_range = [0.5, 1.0]
        node_size = 40
        show_colorbar_nodes = true
        show_colorbar_edges = true
        show_ct_markers = true
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # "plot" セクションだけを取り出す前提
    return data.get("plot", {})


def _build_hover_text(name: str, props: Mapping[str, Any] | None) -> str:
    """ホバー時に表示するテキストを組み立てる簡単なヘルパー."""
    lines: List[str] = [name]
    if props:
        for k, v in props.items():
            lines.append(f"{k}: {v}")
    return "<br>".join(lines)


def _min_max(values: Iterable[float | None]) -> Tuple[float | None, float | None]:
    """None を除外した上での (min, max) を返す。値が空なら (None, None)。"""
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    return min(vals), max(vals)


def _truncate_colorscale(
    colorscale: str | Sequence[str] | Sequence[Tuple[float, str]],
    low: float,
    high: float,
    n_samples: int = 10,
):
    """
    colorscale の一部 [low, high] だけを取り出し、0〜1 に張り直した新しい colorscale を作る。

    例: low=0.5, high=1.0 で「濃い方の半分だけ」など。
    """
    low = max(0.0, min(low, 1.0))
    high = max(0.0, min(high, 1.0))
    if high <= low:
        high = min(1.0, low + 1e-6)

    positions = [
        low + (high - low) * i / (n_samples - 1)
        for i in range(n_samples)
    ]
    # ← ここでは「元の」colorscale を使ってサンプリング
    cols = px.colors.sample_colorscale(colorscale, positions)
    return [(i / (n_samples - 1), c) for i, c in enumerate(cols)]


def _ensure_range_tuple(
    value: Sequence[float] | Tuple[float, float] | None,
    default: Tuple[float, float],
) -> Tuple[float, float]:
    if value is None:
        return default
    return (float(value[0]), float(value[1]))


def _resolve_effective_colorscale(
    colorscale: str | Sequence[str] | Sequence[Tuple[float, str]],
    range_limits: Tuple[float, float],
):
    """Apply range trimming only when the requested window is partial."""
    low, high = range_limits
    if low <= 0.0 and high >= 1.0:
        return colorscale
    return _truncate_colorscale(colorscale, low, high)


def _extract_value_range(
    values: Sequence[float | None],
    cmin_override: float | None,
    cmax_override: float | None,
) -> Tuple[float | None, float | None]:
    vmin, vmax = _min_max(values)
    if cmin_override is not None:
        vmin = cmin_override
    if cmax_override is not None:
        vmax = cmax_override
    return vmin, vmax


def _create_value_to_color_mapper(
    colorscale: str | Sequence[str] | Sequence[Tuple[float, str]],
    range_limits: Tuple[float, float],
    vmin: float | None,
    vmax: float | None,
    fallback: str = "#888888",
):
    """Return mapper that clamps values and samples the requested colorscale."""
    low, high = range_limits

    def _mapper(value: float | None) -> str:
        if value is None or vmin is None or vmax is None:
            return fallback
        if math.isclose(vmax, vmin):
            ratio = 0.5
        else:
            ratio = (value - vmin) / (vmax - vmin)
        ratio = max(0.0, min(1.0, ratio))
        mapped = low + (high - low) * ratio
        mapped = max(0.0, min(1.0, mapped))
        return px.colors.sample_colorscale(colorscale, [mapped])[0]

    return _mapper


def _build_param_styles(
    overrides: Mapping[str, Mapping[str, Any]] | None,
    base_style: ColorStyle,
) -> Dict[str, ColorStyle]:
    result: Dict[str, ColorStyle] = {}
    if not overrides:
        return result
    for key, raw in overrides.items():
        colorscale = raw.get("colorscale", base_style.colorscale)
        colorscale_range = _ensure_range_tuple(
            raw.get("colorscale_range"), base_style.colorscale_range
        )
        cmin = raw.get("cmin", base_style.cmin)
        cmax = raw.get("cmax", base_style.cmax)
        result[key] = ColorStyle(colorscale, colorscale_range, cmin, cmax)
    return result


def _build_node_trace(
    qubits: Sequence[QubitId],
    node_positions: Mapping[QubitId, Coord],
    node_props: Mapping[QubitId, NodeProps],
    node_color_key: str | None,
    node_size: float,
    node_colorscale,
    node_cmin: float | None,
    node_cmax: float | None,
    show_colorbar_nodes: bool,
    node_label_font_size: int,
    node_label_font_color: str,
    node_label_font_family: str | None,
):
    x_nodes: List[float] = []
    y_nodes: List[float] = []
    node_hover: List[str] = []
    node_color_values: List[float | None] = []

    for q in qubits:
        x, y = node_positions[q]
        x_nodes.append(x)
        y_nodes.append(y)
        node_hover.append(_build_hover_text(f"q{q}", node_props.get(q, {})))

        if node_color_key is not None:
            node_color_values.append(node_props.get(q, {}).get(node_color_key, None))
        else:
            node_color_values.append(None)

    node_vmin, node_vmax = _extract_value_range(
        node_color_values, node_cmin, node_cmax
    )

    if node_color_key is not None and node_vmin is not None and node_vmax is not None:
        node_marker = dict(
            size=node_size,
            color=node_color_values,
            colorscale=node_colorscale,
            cmin=node_vmin,
            cmax=node_vmax,
            showscale=show_colorbar_nodes,
            colorbar=dict(
                title=node_color_key,
                x=1.05,
                xanchor="center",
                y=0.5,
                len=1.0,
            ),
            opacity=1.0,
        )
    else:
        node_marker = dict(
            size=node_size,
            color="#1f77b4",
            opacity=1.0,
        )

    node_label_font: Dict[str, Any] = dict(
        size=node_label_font_size,
        color=node_label_font_color,
    )
    if node_label_font_family is not None:
        node_label_font["family"] = node_label_font_family

    node_trace = go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode="markers+text",
        text=[f"<b>{q}</b>" for q in qubits],
        textposition="middle center",
        textfont=node_label_font,
        hoverinfo="text",
        hovertext=node_hover,
        marker=node_marker,
        showlegend=False,
        name="NODE_TRACE",
    )

    return node_trace


def _build_edge_elements(
    edges: Sequence[Tuple[QubitId, QubitId]],
    node_positions: Mapping[QubitId, Coord],
    edge_props: EdgeProps,
    edge_color_key: str | None,
    edge_label_key: str | None,
    edge_colorscale,
    edge_colorscale_range: Tuple[float, float],
    edge_cmin: float | None,
    edge_cmax: float | None,
    edge_label_font_size: int,
    edge_label_offset_frac: float,
):
    edge_traces: List[go.Scatter] = []
    annotations: List[dict] = []

    if edge_color_key is not None:
        edge_color_values: List[float | None] = [
            edge_props.get((c, t), {}).get(edge_color_key, None)
            for (c, t) in edges
        ]
    else:
        edge_color_values = []

    edge_vmin, edge_vmax = _extract_value_range(
        edge_color_values, edge_cmin, edge_cmax
    )
    edge_to_color = _create_value_to_color_mapper(
        edge_colorscale, edge_colorscale_range, edge_vmin, edge_vmax
    )

    for (c, t) in edges:
        x0, y0 = node_positions[c]
        x1, y1 = node_positions[t]

        props = edge_props.get((c, t), {})
        hover_text = _build_hover_text(f"{c} → {t}", props)
        color_value = props.get(edge_color_key, None) if edge_color_key else None
        line_color = edge_to_color(color_value)

        edge_traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(width=6, color=line_color),
                hoverinfo="text",
                hovertext=[hover_text, hover_text],
                showlegend=False,
            )
        )

        if edge_label_key is not None and edge_label_key in props:
            label = props[edge_label_key]

            dx = x1 - x0
            dy = y1 - y0
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            nx, ny = -uy, ux

            if abs(dx) >= abs(dy):
                if ny < 0:
                    nx, ny = -nx, -ny
            else:
                if nx < 0:
                    nx, ny = -nx, -ny

            xm = (x0 + x1) / 2
            ym = (y0 + y1) / 2

            xl = xm + nx * edge_label_offset_frac * length
            yl = ym + ny * edge_label_offset_frac * length

            angle_deg = math.degrees(math.atan2(dy, dx))
            if abs(dx) < abs(dy):
                angle_deg = 90.0
            else:
                if angle_deg < -90.0:
                    angle_deg += 180.0
                elif angle_deg > 90.0:
                    angle_deg -= 180.0

            label_hover = _build_hover_text(f"{c} → {t}", props)

            annotations.append(
                dict(
                    x=xl,
                    y=yl,
                    xref="x",
                    yref="y",
                    text=str(label),
                    showarrow=False,
                    textangle=angle_deg,
                    font=dict(size=edge_label_font_size),
                    hovertext=label_hover,
                    hoverlabel=dict(bgcolor="white"),
                    ax=0,
                    ay=0,
                )
            )

    return edge_traces, annotations, edge_vmin, edge_vmax


def _build_ct_trace(
    edges: Sequence[Tuple[QubitId, QubitId]],
    node_positions: Mapping[QubitId, Coord],
    ct_font_size: int,
    ct_font_color: str,
    ct_offset_along_frac: float,
    ct_offset_normal_frac: float,
):
    if not edges:
        return None

    xs: List[float] = []
    ys: List[float] = []
    texts: List[str] = []
    hovers: List[str] = []

    for c, t in edges:
        xc, yc = node_positions[c]
        xt, yt = node_positions[t]

        dx = xt - xc
        dy = yt - yc
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        cx = xc + ux * ct_offset_along_frac * length + nx * ct_offset_normal_frac * length
        cy = yc + uy * ct_offset_along_frac * length + ny * ct_offset_normal_frac * length
        xs.append(cx)
        ys.append(cy)
        texts.append("C")
        hovers.append(f"control: q{c} → q{t}")

        tx = xt - ux * ct_offset_along_frac * length + nx * ct_offset_normal_frac * length
        ty = yt - uy * ct_offset_along_frac * length + ny * ct_offset_normal_frac * length
        xs.append(tx)
        ys.append(ty)
        texts.append("T")
        hovers.append(f"target: q{c} → q{t}")

    return go.Scatter(
        x=xs,
        y=ys,
        mode="text",
        text=texts,
        textposition="middle center",
        textfont=dict(size=ct_font_size, color=ct_font_color),
        hoverinfo="text",
        hovertext=hovers,
        showlegend=False,
    )


def _add_edge_colorbar_trace(
    fig: go.Figure,
    edge_color_key: str | None,
    edge_colorscale,
    edge_vmin: float | None,
    edge_vmax: float | None,
    show_colorbar_edges: bool,
):
    if (
        not show_colorbar_edges
        or edge_color_key is None
        or edge_vmin is None
        or edge_vmax is None
    ):
        return None

    dummy_vals = [edge_vmin, edge_vmax]
    trace = go.Scatter(
        x=[None, None],
        y=[None, None],
        mode="markers",
        marker=dict(
            size=0.1,
            color=dummy_vals,
            colorscale=edge_colorscale,
            cmin=edge_vmin,
            cmax=edge_vmax,
            showscale=True,
            colorbar=dict(
                title=edge_color_key,
                x=1.30,
                xanchor="center",
                y=0.5,
                len=1.0,
            ),
        ),
        hoverinfo="skip",
        showlegend=False,
    )
    fig.add_trace(trace)
    return trace

def plot_coupling_map_advanced(
    qubits: Sequence[QubitId],
    edges: Sequence[Tuple[QubitId, QubitId]],
    node_positions: Mapping[QubitId, Coord],
    node_props: Mapping[QubitId, NodeProps] | None = None,
    edge_props: EdgeProps | None = None,
    node_color_key: str | None = None,
    edge_color_key: str | None = None,
    edge_label_key: str | None = None,
    node_size: float = 40,
    # 共通デフォルト
    colorscale: str = "Viridis",
    colorscale_range: Tuple[float, float] = (0.0, 1.0),
    # ノード用（未指定なら上のデフォルトを流用）
    node_colorscale: str | None = None,
    node_colorscale_range: Tuple[float, float] | None = None,
    # エッジ用（未指定なら上のデフォルトを流用）
    edge_colorscale: str | None = None,
    edge_colorscale_range: Tuple[float, float] | None = None,
    # カラースケールの min/max を任意指定
    node_cmin: float | None = None,
    node_cmax: float | None = None,
    edge_cmin: float | None = None,
    edge_cmax: float | None = None,
    # 見た目系
    title: str = "Coupling map",
    show_colorbar_nodes: bool = True,
    show_colorbar_edges: bool = False,
    show_ct_markers: bool = True,
    # ラベル・フォント系
    node_label_font_size: int = 14,
    node_label_font_color: str = "white",
    node_label_font_family: str | None = None,
    edge_label_font_size: int = 12,
    edge_label_offset_frac: float = 0.075,
    ct_font_size: int = 10,
    ct_font_color: str = "#333333",
    ct_offset_along_frac: float = 0.10,
    ct_offset_normal_frac: float = 0.05,
    # 図のサイズ
    figure_width: int = 600,
    figure_height: int = 600,
) -> go.Figure:
    """
    Plotly を使って、簡易的な「高機能 coupling map」を描画する。

    - colorscale_range: (low, high) で 0〜1 の一部だけ使う（全体デフォルト）
    - node_colorscale(_range), edge_colorscale(_range):
        ノード/エッジごとに個別のカラーマップ・範囲を指定可能
    - node_cmin/cmax, edge_cmin/cmax:
        カラーバーの表示範囲を明示的に指定したいとき用
    """

    node_props = node_props or {}
    edge_props = edge_props or {}

    # --------------------------
    # colorscale の分離設定
    # --------------------------
    if node_colorscale is None:
        node_colorscale = colorscale
    if node_colorscale_range is None:
        node_colorscale_range = colorscale_range

    if edge_colorscale is None:
        edge_colorscale = colorscale
    if edge_colorscale_range is None:
        edge_colorscale_range = colorscale_range

    node_effective_colorscale = _resolve_effective_colorscale(
        node_colorscale, node_colorscale_range
    )
    edge_effective_colorscale = _resolve_effective_colorscale(
        edge_colorscale, edge_colorscale_range
    )

    node_trace = _build_node_trace(
        qubits=qubits,
        node_positions=node_positions,
        node_props=node_props,
        node_color_key=node_color_key,
        node_size=node_size,
        node_colorscale=node_effective_colorscale,
        node_cmin=node_cmin,
        node_cmax=node_cmax,
        show_colorbar_nodes=show_colorbar_nodes,
        node_label_font_size=node_label_font_size,
        node_label_font_color=node_label_font_color,
        node_label_font_family=node_label_font_family,
    )

    edge_traces, annotations, edge_vmin, edge_vmax = _build_edge_elements(
        edges=edges,
        node_positions=node_positions,
        edge_props=edge_props,
        edge_color_key=edge_color_key,
        edge_label_key=edge_label_key,
        edge_colorscale=edge_colorscale,
        edge_colorscale_range=edge_colorscale_range,
        edge_cmin=edge_cmin,
        edge_cmax=edge_cmax,
        edge_label_font_size=edge_label_font_size,
        edge_label_offset_frac=edge_label_offset_frac,
    )

    ct_trace = None
    if show_ct_markers:
        ct_trace = _build_ct_trace(
            edges=edges,
            node_positions=node_positions,
            ct_font_size=ct_font_size,
            ct_font_color=ct_font_color,
            ct_offset_along_frac=ct_offset_along_frac,
            ct_offset_normal_frac=ct_offset_normal_frac,
        )

    # --------------------------
    # Figure 組み立て
    # --------------------------
    traces = [*edge_traces]
    if ct_trace is not None:
        traces.append(ct_trace)
    traces.append(node_trace)

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title,
        title_x=0.5,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        width=figure_width,
        height=figure_height,
        annotations=annotations,
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    _add_edge_colorbar_trace(
        fig=fig,
        edge_color_key=edge_color_key,
        edge_colorscale=edge_effective_colorscale,
        edge_vmin=edge_vmin,
        edge_vmax=edge_vmax,
        show_colorbar_edges=show_colorbar_edges,
    )

    return fig


def add_node_color_dropdown(
    fig: go.Figure,
    qubits,
    node_props,
    node_color_keys,
    show_colorbar_nodes: bool,
    node_color_param_styles: Mapping[str, ColorStyle] | None = None,
    node_base_style: ColorStyle | None = None,
) -> go.Figure:
    """
    ノード色をプルダウンで切り替える。

    - "NODE_TRACE" という name を持つ trace をベースにする
    - その trace に反映済みの colorscale / colorbar 位置など
      （＝TOML で設定した見た目）をそのまま引き継ぐ
    - key ごとに値だけ変えたノード trace を複数作り、visible で切り替える
    """

    # 1. ベースとなる NODE_TRACE を探す
    node_trace_index = None
    for i, tr in enumerate(fig.data):
        if getattr(tr, "name", None) == "NODE_TRACE":
            node_trace_index = i
            break

    if node_trace_index is None:
        print("WARNING: NODE_TRACE not found, skip dropdown.")
        return fig

    param_styles = node_color_param_styles or {}
    node_trace_indices: list[int] = []
    key_to_trace_index: Dict[str, int] = {}
    base_trace = fig.data[node_trace_index]
    base_marker = base_trace.marker

    # 2. カラーバー位置や colorscale は base_marker からそのまま使う
    colorscale = getattr(base_marker, "colorscale", "Viridis")
    cb = getattr(base_marker, "colorbar", None)
    cb_x = getattr(cb, "x", 1.05)
    cb_y = getattr(cb, "y", 0.5)
    cb_len = getattr(cb, "len", 1.0)

    base_style = node_base_style or ColorStyle(
        colorscale=colorscale,
        colorscale_range=(0.0, 1.0),
        cmin=getattr(base_marker, "cmin", None),
        cmax=getattr(base_marker, "cmax", None),
    )

    # 元の NODE_TRACE は非表示にし、カラーバーも消しておく
    base_trace.visible = False
    if hasattr(base_marker, "showscale"):
        base_marker.showscale = False

    # 3. 各 node_color_key ごとに新しい node trace を作る
    for key in node_color_keys:
        vals = [node_props.get(q, {}).get(key, None) for q in qubits]
        vmin, vmax = _extract_value_range(vals, None, None)
        if vmin is None or vmax is None:
            continue

        style = param_styles.get(key, base_style)
        effective_colorscale = _resolve_effective_colorscale(
            style.colorscale, style.colorscale_range
        )

        marker_cmin = style.cmin if style.cmin is not None else vmin
        marker_cmax = style.cmax if style.cmax is not None else vmax

        new_marker = dict(
            size=base_marker.size,
            color=vals,
            colorscale=effective_colorscale,
            cmin=marker_cmin,
            cmax=marker_cmax,
            showscale=show_colorbar_nodes,
            colorbar=dict(
                title=key,
                x=cb_x,
                y=cb_y,
                len=cb_len,
            ),
        )

        new_trace = go.Scatter(
            x=base_trace.x,
            y=base_trace.y,
            mode=base_trace.mode,
            text=base_trace.text,
            textposition=base_trace.textposition,
            textfont=base_trace.textfont,
            hoverinfo=base_trace.hoverinfo,
            hovertext=base_trace.hovertext,
            marker=new_marker,
            showlegend=False,
            visible=False,
            name=f"NODE_TRACE_{key}",
        )
        fig.add_trace(new_trace)
        trace_index = len(fig.data) - 1
        node_trace_indices.append(trace_index)
        key_to_trace_index[key] = trace_index

    if not node_trace_indices:
        return fig

    # 最初の候補だけ表示
    fig.data[node_trace_indices[0]].visible = True

    # 4. updatemenus で visible を切り替える
    buttons = []
    for key in node_color_keys:
        target_trace_id = key_to_trace_index.get(key)
        if target_trace_id is None:
            continue

        visible_subset = [trace_idx == target_trace_id for trace_idx in node_trace_indices]

        buttons.append(
            dict(
                label=key,
                method="restyle",
                args=[{"visible": visible_subset}, node_trace_indices],
            )
        )

    if not buttons:
        return fig

    # カラーバーの “上あたり” に置きたいので、x は colorbar.x に合わせて、
    # y は 1.08 くらいにして少し上に出す（y>1 でもOK）
    menu_y = 1.01

    # 既存の updatemenus がある（エッジ側で追加済み）の可能性があるので append する
    menus = list(fig.layout.updatemenus) if fig.layout.updatemenus else []
    menus.append(
        dict(
            buttons=buttons,
            direction="down",
            showactive=True,
            x=cb_x,              # ★ カラーバーと横位置を揃える
            y=menu_y,            # ★ 上に少し出す
            xanchor="center",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
        )
    )
    fig.update_layout(updatemenus=menus)

    return fig


def add_edge_color_dropdown(
    fig: go.Figure,
    qubits,
    edges,
    node_positions,
    edge_props,
    edge_color_keys,
    show_colorbar_edges: bool = True,
    edge_color_param_styles: Mapping[str, ColorStyle] | None = None,
    edge_base_style: ColorStyle | None = None,
) -> go.Figure:
    """
    エッジの色をプルダウンで切り替える。

    アプローチ:
      - もともとの edge trace（最初の len(edges) 本）を非表示にする
      - edge_color_keys ごとに「新しい edge trace 群 + カラーバー trace」を追加
      - updatemenus で visible を切り替える
    """

    if not edge_color_keys:
        return fig

    edge_cb_x = 1.30
    edge_cb_y = 0.5
    edge_cb_len = 1.0

    param_styles = edge_color_param_styles or {}
    base_style = edge_base_style or ColorStyle(
        colorscale="Viridis",
        colorscale_range=(0.0, 1.0),
        cmin=None,
        cmax=None,
    )

    # --- 1. もともとの edge trace を非表示にする ---
    num_edges = len(edges)
    base_edge_indices = list(range(num_edges))
    for idx in base_edge_indices:
        fig.data[idx].visible = False

    # もともとの edge カラーバー（ダミー trace）があれば潰す
    base_edge_colorbar_index = None
    for i, tr in enumerate(fig.data):
        if (
            isinstance(tr, go.Scatter)
            and tr.mode == "markers"
            and len(tr.x) == 2
            and getattr(tr.marker, "size", None) == 0.1
            and getattr(tr.marker, "showscale", False)
            and tr.hoverinfo == "skip"
            and not tr.showlegend
        ):
            base_edge_colorbar_index = i
            tr.visible = False
            tr.marker.showscale = False

    # すべての edge 関連 trace index を集めておく
    all_edge_related: set[int] = set(base_edge_indices)
    if base_edge_colorbar_index is not None:
        all_edge_related.add(base_edge_colorbar_index)

    # 各キーごとの edge trace 群の index リスト
    edge_groups: list[list[int]] = []

    for key in edge_color_keys:
        vals = [edge_props.get((c, t), {}).get(key, None) for (c, t) in edges]
        style = param_styles.get(key, base_style)
        vmin, vmax = _extract_value_range(vals, style.cmin, style.cmax)

        if vmin is None or vmax is None:
            edge_groups.append([])
            continue

        val_to_color = _create_value_to_color_mapper(
            style.colorscale,
            style.colorscale_range,
            vmin,
            vmax,
        )

        group_indices: list[int] = []

        # --- edge line 群を追加 ---
        for (c, t), v in zip(edges, vals):
            x0, y0 = node_positions[c]
            x1, y1 = node_positions[t]
            props = edge_props.get((c, t), {})
            hover_text = _build_hover_text(f"{c} → {t}", props)
            line_color = val_to_color(v)

            tr = go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(width=6, color=line_color),
                hoverinfo="text",
                hovertext=[hover_text, hover_text],
                showlegend=False,
                visible=False,
                name=f"EDGE_{key}",
            )
            fig.add_trace(tr)
            idx = len(fig.data) - 1
            group_indices.append(idx)
            all_edge_related.add(idx)

        # --- カラーバー用のダミー trace ---
        if show_colorbar_edges:
            dummy_vals = [vmin, vmax]
            effective_colorscale = _resolve_effective_colorscale(
                style.colorscale, style.colorscale_range
            )
            dummy_trace = go.Scatter(
                x=[None, None],
                y=[None, None],
                mode="markers",
                marker=dict(
                    size=0.1,
                    color=dummy_vals,
                    colorscale=effective_colorscale,
                    cmin=vmin,
                    cmax=vmax,
                    showscale=True,
                    colorbar=dict(
                        title=key,
                        x=1.30,
                        y=0.5,
                        len=1.0,
                    ),
                ),
                hoverinfo="skip",
                showlegend=False,
                visible=False,
                name=f"EDGE_COLORBAR_{key}",
            )
            fig.add_trace(dummy_trace)
            idx = len(fig.data) - 1
            group_indices.append(idx)
            all_edge_related.add(idx)

            # ★ ここで実際の位置を覚える（TOMLで変えても追随する）
            cb = dummy_trace.marker.colorbar
            edge_cb_x = getattr(cb, "x", edge_cb_x)
            edge_cb_y = getattr(cb, "y", edge_cb_y)
            edge_cb_len = getattr(cb, "len", edge_cb_len)

        edge_groups.append(group_indices)

    # ここでもう一度 baseline を取り直す（新規 trace 追加後）
    # base_visible = [
    #     (tr.visible if tr.visible is not None else True) for tr in fig.data
    # ]

    # 最初に表示するグループ（非空の最初）
    first_group_idx = next(
        (i for i, g in enumerate(edge_groups) if g), None
    )
    if first_group_idx is not None:
        for idx in edge_groups[first_group_idx]:
            fig.data[idx].visible = True

    # --- updatemenus を追加（既存があればそれに追加） ---
    menus = list(fig.layout.updatemenus) if fig.layout.updatemenus else []

    buttons = []

    # restyle 用に、エッジ関連 trace の index をソートして固定順にしておく
    edge_indices_sorted = sorted(all_edge_related)

    for key, group in zip(edge_color_keys, edge_groups):
        if not group:
            continue

        # edge_indices_sorted に対応する visible の配列を作る
        values: list[bool] = []
        group_set = set(group)
        for idx in edge_indices_sorted:
            values.append(idx in group_set)

        buttons.append(
            dict(
                label=key,
                method="restyle",
                args=[
                    {"visible": values},   # この visible を
                    edge_indices_sorted,   # edge 関連 trace にだけ適用
                ],
            )
        )

    if buttons:
        # カラーバーの “上あたり” に置く
        menu_y = 1.01

        menus.append(
            dict(
                buttons=buttons,
                direction="down",
                showactive=True,
                x=edge_cb_x,       # ★ エッジ用カラーバーの x と揃える
                y=menu_y,
                xanchor="center",
                yanchor="bottom",
                bgcolor="rgba(255,255,255,0.7)",
                bordercolor="rgba(0,0,0,0.2)",
                borderwidth=1,
            )
        )
        fig.update_layout(updatemenus=menus)

    return fig



def main() -> None:
    qubits = [0, 1, 2, 3, 4, 5, 6, 7]
    node_positions: Dict[int, Coord] = {
        0: (0, 0),
        1: (1, 0),
        2: (0, 1),
        3: (1, 1),
        4: (2, 0),
        5: (3, 0),
        6: (2, 1),
        7: (3, 1),
    }
    edges = [(0, 1), (0, 2), (3, 1), (3, 2),
             (4, 5), (4, 6), (7, 5), (7, 6),
             (4, 1), (3, 6)]

    node_props: Dict[int, Dict[str, float]] = {
        0: {"freq_GHz": 5.1, "T1_us": 80},
        1: {"freq_GHz": 5.2, "T1_us": 70},
        2: {"freq_GHz": 5.0, "T1_us": 90},
        3: {"freq_GHz": 5.3, "T1_us": 60},
        4: {"freq_GHz": 5.1, "T1_us": 75},
        5: {"freq_GHz": 5.2, "T1_us": 65},
        6: {"freq_GHz": 5.0, "T1_us": 85},
        7: {"freq_GHz": 5.3, "T1_us": 55},
    }

    edge_props: EdgeProps = {
        (0, 1): {"cx_error": 1.0e-2, "duration_ns": 200},
        (0, 2): {"cx_error": 5.0e-3, "duration_ns": 220},
        (3, 1): {"cx_error": 8.0e-3, "duration_ns": 210},
        (3, 2): {"cx_error": 1.2e-2, "duration_ns": 230},
        (4, 5): {"cx_error": 9.0e-3, "duration_ns": 200},
        (4, 6): {"cx_error": 4.0e-3, "duration_ns": 220},
        (7, 5): {"cx_error": 7.0e-3, "duration_ns": 210},
        (7, 6): {"cx_error": 1.1e-2, "duration_ns": 230},
        (4, 1): {"cx_error": 1.3e-2, "duration_ns": 240},
        (3, 6): {"cx_error": 6.0e-3, "duration_ns": 225},
    }

    # --- TOML 設定読込 (Task5) ---
    try:
        cfg = load_plot_config("config.toml")
    except FileNotFoundError:
        cfg = {}

    # range 系は list で書かれてくるので tuple に変換
    def _get_range(name: str, default: Tuple[float, float] | None = None):
        v = cfg.get(name)
        if v is None:
            return default
        return (float(v[0]), float(v[1]))

    base_range = _get_range("colorscale_range", (0.5, 1.0))
    default_colorscale = cfg.get("colorscale", "plasma_r")

    node_range = _get_range("node_colorscale_range") or base_range
    edge_range = _get_range("edge_colorscale_range") or base_range

    node_base_style = ColorStyle(
        colorscale=cfg.get("node_colorscale", default_colorscale),
        colorscale_range=node_range,
        cmin=cfg.get("node_cmin"),
        cmax=cfg.get("node_cmax"),
    )
    edge_base_style = ColorStyle(
        colorscale=cfg.get("edge_colorscale", default_colorscale),
        colorscale_range=edge_range,
        cmin=cfg.get("edge_cmin"),
        cmax=cfg.get("edge_cmax"),
    )

    node_param_styles = _build_param_styles(
        cfg.get("node_color_params"), node_base_style
    )
    edge_param_styles = _build_param_styles(
        cfg.get("edge_color_params"), edge_base_style
    )

    default_node_key = cfg.get("node_color_key", "T1_us")
    default_edge_key = cfg.get("edge_color_key", "cx_error")

    node_style_for_plot = node_param_styles.get(default_node_key, node_base_style)
    edge_style_for_plot = edge_param_styles.get(default_edge_key, edge_base_style)

    show_colorbar_nodes = cfg.get("show_colorbar_nodes", True)
    show_colorbar_edges = cfg.get("show_colorbar_edges", True)

    fig = plot_coupling_map_advanced(
        qubits=qubits,
        edges=edges,
        node_positions=node_positions,
        node_props=node_props,
        edge_props=edge_props,
        node_color_key=default_node_key,
        edge_color_key=default_edge_key,
        edge_label_key=cfg.get("edge_label_key", "cx_error"),
        node_size=cfg.get("node_size", 40),

        colorscale=default_colorscale,
        colorscale_range=base_range,
        node_colorscale=node_style_for_plot.colorscale,
        node_colorscale_range=node_style_for_plot.colorscale_range,
        edge_colorscale=edge_style_for_plot.colorscale,
        edge_colorscale_range=edge_style_for_plot.colorscale_range,

        node_cmin=node_style_for_plot.cmin,
        node_cmax=node_style_for_plot.cmax,
        edge_cmin=edge_style_for_plot.cmin,
        edge_cmax=edge_style_for_plot.cmax,

        title=cfg.get("title", "Example backend (T1 / CNOT error)"),
        show_colorbar_nodes=show_colorbar_nodes,
        show_colorbar_edges=show_colorbar_edges,
        show_ct_markers=cfg.get("show_ct_markers", True),

        node_label_font_size=cfg.get("node_label_font_size", 14),
        node_label_font_color=cfg.get("node_label_font_color", "white"),
        node_label_font_family=cfg.get("node_label_font_family"),
        edge_label_font_size=cfg.get("edge_label_font_size", 12),
        edge_label_offset_frac=cfg.get("edge_label_offset_frac", 0.075),

        ct_font_size=cfg.get("ct_font_size", 10),
        ct_font_color=cfg.get("ct_font_color", "#333333"),
        ct_offset_along_frac=cfg.get("ct_offset_along_frac", 0.10),
        ct_offset_normal_frac=cfg.get("ct_offset_normal_frac", 0.05),

        figure_width=cfg.get("figure_width", 600),
        figure_height=cfg.get("figure_height", 600),
    )

    # --- ★ エッジ側ドロップダウンを追加 ---
    dropdown_edge_keys = cfg.get("edge_color_keys")
    if dropdown_edge_keys is None:
        edge_color_keys = [default_edge_key]
    else:
        edge_color_keys = list(dropdown_edge_keys)

    fig = add_edge_color_dropdown(
        fig,
        qubits=qubits,
        edges=edges,
        node_positions=node_positions,
        edge_props=edge_props,
        edge_color_keys=edge_color_keys,
        show_colorbar_edges=show_colorbar_edges,
        edge_color_param_styles=edge_param_styles,
        edge_base_style=edge_base_style,
    )

    
    # --- ★ ここからドロップダウン用設定を TOML から取得 ---
    # デフォルト: node_color_key だけを候補にする
    dropdown_keys = cfg.get("node_color_keys")  # TOML で複数指定できるようにする
    if dropdown_keys is None:
        node_color_keys = [default_node_key]
    else:
        # TOML 側で ["T1_us", "freq_GHz"] みたいに書いておく想定
        node_color_keys = list(dropdown_keys)

    fig = add_node_color_dropdown(
        fig,
        qubits=qubits,
        node_props=node_props,
        node_color_keys=node_color_keys,
        show_colorbar_nodes=show_colorbar_nodes,
        node_color_param_styles=node_param_styles,
        node_base_style=node_base_style,
    )

    fig.write_html("build/sample.html")


if __name__ == "__main__":

    main()