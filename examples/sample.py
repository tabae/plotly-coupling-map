import os
import json
import math
import random
import requests
from plotly_coupling_map.plotly_coupling_map import plotly_coupling_map

# Sample data for testing
#
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


if os.path.exists("examples/device_topology_sim.json"):
    print("Load local device-topology_sim.json")
    with open("examples/device_topology_sim.json", "r") as f:
        device_topology = json.load(f)
else:
    print("Download device-topology.json from GitHub")
    reps = requests.get("https://raw.githubusercontent.com/oqtopus-team/device-gateway/refs/heads/develop/config/example/device_topology_sim.json")
    reps.raise_for_status()
    device_topology = reps.json()
    with open("examples/device_topology_sim.json", "w") as f:
        json.dump(device_topology, f, indent=2)

qubits = []
node_positions = {}
edges = []
node_props = {}
edge_props = {}

def noise(min_val, max_val, digits=0):
    raw_val = random.uniform(min_val, max_val)
    if digits == 0:
        return round(raw_val)
    return math.floor(raw_val * 10**digits) / 10**digits

for qubit in device_topology["qubits"]:
    qubit_id = qubit["id"]
    qubits.append(qubit_id)
    node_positions[qubit_id] = (qubit["position"]["x"], qubit["position"]["y"])
    node_props[qubit_id] = {
        "physical_id": qubit["physical_id"],
        "position": qubit["position"],
        "readout_error": qubit["meas_error"]["readout_assignment_error"] + noise(0, 0.1, 4),
        "1q_fidelity": qubit["fidelity"] + noise(-0.01, 0.0, 4),
        "t1": qubit["qubit_lifetime"]["t1"] + noise(-30, 50),
        "t2": qubit["qubit_lifetime"]["t2"] + noise(-70, -30),
        "gate_duration": qubit["gate_duration"],
    }

for coupling in device_topology["couplings"]:
    control = coupling["control"]
    target = coupling["target"]
    edges.append((control, target))
    edge_props[(control, target)] = {
        "2q_fidelity": coupling["fidelity"] + noise(-0.01, 0.009, 4),
        "cx_duration": coupling["gate_duration"]["cx"] + noise(-20, 20),
        "rzx90_duration": coupling["gate_duration"]["rzx90"] + noise(-20, 20),
    }

plotly_coupling_map(qubits,
                  node_positions,
                  edges,
                  node_props,
                  edge_props,
                  filename="docs/index.html",
                  config_file="examples/sample.toml",)

# Add extra HTML link to the generated file
extra_html = """
<div style="margin-top: 40px; text-align: center; font-size: 12px;">
  <a href="https://github.com/oqtopus-team/device-gateway/blob/develop/config/example/device_topology_sim.json" target="_blank">
    Source of device topology data
  </a>
</div>
"""
with open("docs/index.html", "r", encoding="utf-8") as f:
    html = f.read()
html = html.replace("</body>", extra_html + "\n</body>")
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)