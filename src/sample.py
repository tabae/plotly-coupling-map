import os
import json
import math
import random
import requests
from plot_coupling_map import plot_coupling_map

# Sample data for testing
#
# qubits = [0, 1, 2, 3, 4, 5, 6, 7]
#
# node_positions = {
#     0: (0, 0),
#     1: (1, 0),
#     2: (0, 1),
#     3: (1, 1),
#     4: (2, 0),
#     5: (3, 0),
#     6: (2, 1),
#     7: (3, 1),
# }
# edges = [(0, 1), (0, 2), (3, 1), (3, 2),
#         (4, 5), (4, 6), (7, 5), (7, 6),
#         (4, 1), (3, 6)]
#
# node_props = {
#     0: {"freq_GHz": 5.1, "T1_us": 80, "T2_us": 70, "readout_error": 2.0e-2, "gate_error": 1.5e-3},
#     1: {"freq_GHz": 5.2, "T1_us": 70, "T2_us": 60, "readout_error": 2.1e-2, "gate_error": 1.6e-3},
#     2: {"freq_GHz": 5.0, "T1_us": 90, "T2_us": 80, "readout_error": 1.9e-2, "gate_error": 1.4e-3},
#     3: {"freq_GHz": 5.3, "T1_us": 60, "T2_us": 50, "readout_error": 2.2e-2, "gate_error": 1.7e-3},
#     4: {"freq_GHz": 5.1, "T1_us": 75, "T2_us": 65, "readout_error": 2.0e-2, "gate_error": 1.5e-3},
#     5: {"freq_GHz": 5.2, "T1_us": 65, "T2_us": 55, "readout_error": 2.1e-2, "gate_error": 1.6e-3},
#     6: {"freq_GHz": 5.0, "T1_us": 85, "T2_us": 75, "readout_error": 1.9e-2, "gate_error": 1.4e-3},
#     7: {"freq_GHz": 5.3, "T1_us": 55, "T2_us": 45, "readout_error": 2.2e-2, "gate_error": 1.7e-3},
# }
#
# edge_props = {
#     (0, 1): {"gate_error": 1.0e-2, "duration_ns": 200},
#     (0, 2): {"gate_error": 5.0e-3, "duration_ns": 220},
#     (3, 1): {"gate_error": 8.0e-3, "duration_ns": 210},
#     (3, 2): {"gate_error": 1.2e-2, "duration_ns": 230},
#     (4, 5): {"gate_error": 9.0e-3, "duration_ns": 200},
#     (4, 6): {"gate_error": 4.0e-3, "duration_ns": 220},
#     (7, 5): {"gate_error": 7.0e-3, "duration_ns": 210},
#     (7, 6): {"gate_error": 1.1e-2, "duration_ns": 230},
#     (4, 1): {"gate_error": 1.3e-2, "duration_ns": 240},
#     (3, 6): {"gate_error": 6.0e-3, "duration_ns": 225},
# }
#
# plot_coupling_map(qubits,
#                     node_positions,
#                     edges,
#                     node_props,
#                     edge_props,
#                     filename="build/sample.html",
#                     config_file="config/sample.toml",)

if os.path.exists("device_topology_sim.json"):
    print("Load local device-topology_sim.json")
    with open("device_topology_sim.json", "r") as f:
        device_topology = json.load(f)
else:
    print("Download device-topology.json from GitHub")
    reps = requests.get("https://raw.githubusercontent.com/oqtopus-team/device-gateway/refs/heads/develop/config/example/device_topology_sim.json")
    reps.raise_for_status()
    device_topology = reps.json()

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

plot_coupling_map(qubits,
                  node_positions,
                  edges,
                  node_props,
                  edge_props,
                  filename="docs/index.html",
                  config_file="config/sample.toml",)

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