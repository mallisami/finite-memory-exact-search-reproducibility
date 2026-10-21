"""Paper-2 helpers for deterministic DeathStarBench shadow-replay environments.

Extracted from the earlier measured-state harness so the Paper-2 reproducibility
package does not need to ship the superseded WfCommons/three-arm confirmation
code.  The functions are byte-equivalent in logic to the helpers used by the
frozen P8 runner: application indexing, deterministic host-envelope
construction, and CSV-manifest loading.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .real_instances import host_network, worst_fit_placement

APP_INDEX = {"socialNetwork": 0, "hotelReservation": 1, "mediaMicroservices": 2}


def environment(demands: np.ndarray, topologies, m: int, rho: float, headroom: float, seed: int):
    rng = np.random.default_rng(seed)
    topo = topologies[int(rng.integers(len(topologies)))]
    cost, _, hosts = host_network(topo, m, rng)
    total = demands.sum(axis=0)
    largest = demands.max(axis=0)
    cap_per = np.maximum(total / (m * rho), largest * headroom)
    multiplier = 1.0
    placement = None
    for attempt in range(30):
        capacities = np.tile(cap_per * multiplier, (m, 1))
        try:
            placement = worst_fit_placement(
                demands, capacities, np.random.default_rng(seed + 1000 + attempt)
            )
            break
        except ValueError:
            multiplier *= 1.05
    if placement is None:
        raise RuntimeError("could not construct common feasible host envelope")
    realized = (total / capacities.sum(axis=0)).tolist()
    return cost, capacities, placement, {
        "topology": topo.name,
        "host_ids": hosts,
        "capacity_multiplier": multiplier,
        "realized_resource_load": realized,
    }


def read_manifest(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
