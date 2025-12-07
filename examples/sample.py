import math
import random
from plotly_coupling_map import plotly_coupling_map

# 量子ビット定義
# qubits = [0, 1, 2, 3]

# # ノードの位置
# node_positions = {
#     0: (0, 0),
#     1: (1, 0),
#     2: (0, 1),
#     3: (1, 1),
# }

# # エッジ（接続）
# edges = [(0, 1), (0, 2), (1, 2), (2, 3)]

# # ノードのプロパティ
# node_props = {
#     0: {"fidelity": 0.998, "t1": 80, "t2": 70, "readout_error": 0.02},
#     1: {"fidelity": 0.997, "t1": 70, "t2": 60, "readout_error": 0.021},
#     2: {"fidelity": 0.996, "t1": 85, "t2": 75, "readout_error": 0.019},
#     3: {"fidelity": 0.995, "t1": 75, "t2": 65, "readout_error": 0.022},
# }

# # エッジのプロパティ
# edge_props = {
#     (0, 1): {"fidelity": 0.99, "gate_error": 0.01, "duration_ns": 200},
#     (0, 2): {"fidelity": 0.995, "gate_error": 0.005, "duration_ns": 220},
#     (1, 2): {"fidelity": 0.992, "gate_error": 0.008, "duration_ns": 210},
#     (2, 3): {"fidelity": 0.991, "gate_error": 0.009, "duration_ns": 215},
# }

# # カップリングマップを生成
# plotly_coupling_map(
#     qubits=qubits,
#     node_positions=node_positions,
#     edges=edges,
#     node_props=node_props,
#     edge_props=edge_props,
#     filename="./coupling_map.html",
#     config_file="examples/sample.toml",
# )

n_rows = 4
n_cols = 6

qubits = list(range(n_rows * n_cols))
node_positions = {}
edges = []
node_props = {}
edge_props = {}


def rng(min_val, max_val, digits=0):
    raw_val = random.uniform(min_val, max_val)
    if digits == 0:
        return round(raw_val)
    return math.floor(raw_val * 10**digits) / 10**digits

for q in qubits:
    row = q // n_cols
    col = q % n_cols
    node_positions[q] = (col, n_rows - row)
    t1 = rng(100, 200)
    node_props[q] = {
        "1q_fidelity": rng(0.98, 0.9999, 4),
        "t1": t1,
        "t2": t1 + rng(-50, -0),
        "readout_error": rng(0.2, 0.001, 4),
    }

for row in range(n_rows):
    for col in range(n_cols):
        for dcol, drow in [(1, 0), (0, 1)]:
            if col + dcol < n_cols and row + drow < n_rows:
                q1 = row * n_cols + col
                q2 = (row + drow) * n_cols + (col + dcol)
                edges.append((q1, q2))
                edge_props[(q1, q2)] = {
                    "2q_fidelity": rng(0.90, 0.999, 4),
                    "duration": rng(100, 300),
                }

plotly_coupling_map(qubits,
                    node_positions,
                    edges,
                    node_props,
                    edge_props,
                    filename="docs/index.html",
                    config_file="examples/sample.toml",)
