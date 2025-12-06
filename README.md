# plotly-coupling-map

> **注意**: このREADMEはGitHub Copilotによって生成されました。

量子コンピューティングデバイスのカップリングマップを、Plotlyを使用してインタラクティブに可視化するPythonライブラリです。

## 特徴

- **インタラクティブな可視化**: Plotlyを使用した、ズームやホバー情報表示が可能な動的なグラフ
- **柔軟なカラーマップ**: ノードとエッジに対して、異なるパラメータや色スケールを適用可能
- **ドロップダウンメニュー**: 複数のパラメータ（フィデリティ、T1、T2、ゲートエラーなど）を切り替えて表示
- **TOML設定ファイル**: 描画パラメータを外部ファイルで簡単にカスタマイズ
- **エッジラベル**: 接続間の重要な指標を視覚的に表示

## インストール

### 依存関係

- Python 3.11以上
- plotly >= 6.5.0
- networkx >= 3.6
- numpy >= 2.3.5

### インストール方法

```bash
pip install plotly networkx numpy
```

または、このリポジトリをクローンして使用：

```bash
git clone https://github.com/tabae/plotly-coupling-map.git
cd plotly-coupling-map
pip install plotly networkx numpy
```

## 使用方法

### 基本的な使い方

```python
from plot_coupling_map import plot_coupling_map

# 量子ビット定義
qubits = [0, 1, 2, 3]

# ノードの位置
node_positions = {
    0: (0, 0),
    1: (1, 0),
    2: (0, 1),
    3: (1, 1),
}

# エッジ（接続）
edges = [(0, 1), (0, 2), (1, 2), (2, 3)]

# ノードのプロパティ
node_props = {
    0: {"fidelity": 0.998, "t1": 80, "t2": 70, "readout_error": 0.02},
    1: {"fidelity": 0.997, "t1": 70, "t2": 60, "readout_error": 0.021},
    2: {"fidelity": 0.996, "t1": 85, "t2": 75, "readout_error": 0.019},
    3: {"fidelity": 0.995, "t1": 75, "t2": 65, "readout_error": 0.022},
}

# エッジのプロパティ
edge_props = {
    (0, 1): {"fidelity": 0.99, "gate_error": 0.01, "duration_ns": 200},
    (0, 2): {"fidelity": 0.995, "gate_error": 0.005, "duration_ns": 220},
    (1, 2): {"fidelity": 0.992, "gate_error": 0.008, "duration_ns": 210},
    (2, 3): {"fidelity": 0.991, "gate_error": 0.009, "duration_ns": 215},
}

# カップリングマップを生成
plot_coupling_map(
    qubits=qubits,
    node_positions=node_positions,
    edges=edges,
    node_props=node_props,
    edge_props=edge_props,
    filename="output/coupling_map.html",
    config_file="config/sample.toml",
)
```

### 設定ファイル（TOML）

`config/sample.toml`を参考に、描画パラメータをカスタマイズできます：

```toml
[plot]
title = "Coupling Map"

# 表示するパラメータ
node_color_key = "fidelity"
edge_color_key = "fidelity"
edge_label_key = "fidelity"

# ドロップダウンで切り替えるパラメータ
edge_color_keys = ["fidelity", "gate_error", "duration_ns"]
node_color_keys = ["fidelity", "readout_error", "t1", "t2"]

# カラースケール設定
colorscale = "plasma_r"
colorscale_range = [0.5, 1.0]

# 図のサイズ
figure_width = 600
figure_height = 600

# パラメータごとの詳細設定
[plot.node_color_params.fidelity]
colorscale = "plasma_r"
colorscale_range = [0.5, 1.0]
cmin = 0.99
cmax = 1.0
```

### サンプルコード

リポジトリには実用的なサンプルコードが含まれています：

```bash
python src/sample.py
```

このスクリプトは、[こちら](https://raw.githubusercontent.com/oqtopus-team/device-gateway/refs/heads/develop/config/example/device_topology_sim.json)のサンプルデータをもとに、カップリングマップを生成して`html/sample.html`に保存します。

## 機能の詳細

### カラーマップのカスタマイズ

- **colorscale**: Plotlyのカラースケール名（"Viridis", "plasma", "plasma_r"など）
- **colorscale_range**: 使用するカラースケールの範囲 [0.0, 1.0]
- **cmin/cmax**: カラーバーの最小値・最大値を明示的に指定

### ドロップダウンメニュー

複数のパラメータを定義すると、インタラクティブなドロップダウンメニューが自動的に追加され、表示するパラメータをリアルタイムで切り替えられます。

### エッジラベル

`edge_label_key`を指定すると、エッジ上にラベルが表示されます。ラベルの位置やフォントサイズは`edge_label_offset_frac`や`edge_label_font_size`で調整可能です。

## プロジェクト構成

```
plotly-coupling-map/
├── src/
│   ├── plot_coupling_map.py  # メインライブラリ
│   └── sample.py              # サンプルスクリプト
├── config/
│   └── sample.toml            # サンプル設定ファイル
├── html/
│   └── sample.html            # 出力例
├── pyproject.toml             # プロジェクト設定
└── README.md                  # このファイル
```

## API リファレンス

### `plot_coupling_map()`

カップリングマップを生成してHTMLファイルとして保存します。

**パラメータ:**
- `qubits`: 量子ビットIDのリスト
- `node_positions`: 各量子ビットの2D座標を持つ辞書
- `edges`: (control, target)のタプルのリスト
- `node_props`: 各ノードのプロパティを持つ辞書
- `edge_props`: 各エッジのプロパティを持つ辞書
- `filename`: 出力HTMLファイルのパス
- `config_file`: TOML設定ファイルのパス

### `load_plot_config()`

TOML設定ファイルから描画パラメータを読み込みます。
