"""Real-data PCR instances: application graphs placed on real network topologies.

Construction (PREREGISTRATION_2026-09-26.md, section 2.2):
  * hosts: ``m`` points of presence sampled (seeded) from one connected,
    geolocated component of an Internet Topology Zoo network; host-to-host
    cost is the shortest-path great-circle distance, divided by the median
    off-diagonal cost of the sampled hosts;
  * capacities: total demand / rho, split across hosts in proportion to
    their degree in the topology;
  * incumbent: capacity-only worst-fit placement (communication-agnostic),
    so repair has real room to improve;
  * multi-tenant clusters: whole applications sampled with replacement until
    n >= target, with no edges between tenants.
Units: workflow volumes in MB and memory in GB (a pure unit choice).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, shortest_path

from .instance import AssignmentInstance

_GRAPHML = "{http://graphml.graphdrawing.org/xmlns}"


@dataclass(frozen=True)
class AppGraph:
    name: str
    interaction: np.ndarray
    demands: np.ndarray


@dataclass(frozen=True)
class Topology:
    name: str
    coords: np.ndarray          # (N, 2) latitude, longitude in degrees
    adjacency: list[tuple[int, int]]


@dataclass(frozen=True)
class RealCase:
    instance: AssignmentInstance
    placement: np.ndarray
    meta: dict


def _haversine_km(a: np.ndarray, b: np.ndarray) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def load_topology(path: Path) -> Topology | None:
    """Largest connected component of geolocated nodes, or None if unusable."""
    root = ET.parse(path).getroot()
    keys = {k.get("id"): k.get("attr.name") for k in root.iter(f"{_GRAPHML}key")}
    graph = root.find(f"{_GRAPHML}graph")
    if graph is None:
        return None
    coords: dict[str, tuple[float, float]] = {}
    for node in graph.iter(f"{_GRAPHML}node"):
        attrs = {keys.get(d.get("key")): d.text for d in node.iter(f"{_GRAPHML}data")}
        try:
            coords[node.get("id")] = (float(attrs["Latitude"]), float(attrs["Longitude"]))
        except (KeyError, TypeError, ValueError):
            continue
    ids = sorted(coords)
    index = {v: i for i, v in enumerate(ids)}
    edges = set()
    for edge in graph.iter(f"{_GRAPHML}edge"):
        s, t = edge.get("source"), edge.get("target")
        if s in index and t in index and s != t:
            edges.add((min(index[s], index[t]), max(index[s], index[t])))
    if len(ids) < 2 or not edges:
        return None
    n = len(ids)
    mat = csr_matrix((np.ones(len(edges)), ([a for a, _ in edges], [b for _, b in edges])), shape=(n, n))
    _, labels = connected_components(mat, directed=False)
    keep = np.flatnonzero(labels == np.bincount(labels).argmax())
    remap = {int(old): new for new, old in enumerate(keep)}
    coords_arr = np.asarray([coords[ids[i]] for i in keep], dtype=float)
    kept_edges = [(remap[a], remap[b]) for a, b in edges if a in remap and b in remap]
    return Topology(path.stem, coords_arr, kept_edges)


def eligible_topologies(directory: Path, min_nodes: int) -> list[Topology]:
    out = []
    for path in sorted(directory.rglob("*.graphml")):
        if path.stem in {"blank", "example"}:
            continue
        topo = load_topology(path)
        if topo is not None and len(topo.coords) >= min_nodes:
            out.append(topo)
    return out


def host_network(topology: Topology, m: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Sample m hosts; return normalized cost matrix, degrees and host ids."""
    n = len(topology.coords)
    rows, cols, weights = [], [], []
    degree = np.zeros(n, dtype=int)
    for a, b in topology.adjacency:
        d = max(_haversine_km(topology.coords[a], topology.coords[b]), 1.0)
        rows += [a, b]
        cols += [b, a]
        weights += [d, d]
        degree[a] += 1
        degree[b] += 1
    dist = shortest_path(csr_matrix((weights, (rows, cols)), shape=(n, n)), directed=False)
    hosts = sorted(int(h) for h in rng.choice(n, size=m, replace=False))
    cost = dist[np.ix_(hosts, hosts)]
    off = cost[~np.eye(m, dtype=bool)]
    cost = cost / float(np.median(off))
    np.fill_diagonal(cost, 0.0)
    return cost, degree[hosts], hosts


def worst_fit_placement(demands: np.ndarray, capacities: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Capacity-only worst-fit: largest normalized demand first, most free host."""
    n = demands.shape[0]
    scale = np.maximum(capacities.max(axis=0), 1e-300)
    order = np.argsort(-(demands / scale).max(axis=1) - 1e-9 * rng.random(n), kind="stable")
    residual = capacities.astype(float).copy()
    placement = np.full(n, -1, dtype=int)
    for i in order:
        fits = np.all(residual >= demands[i][None, :], axis=1)
        if not fits.any():
            raise ValueError("worst-fit could not place every node")
        slack = np.where(fits, (residual / scale).min(axis=1), -np.inf)
        h = int(np.argmax(slack))
        placement[i] = h
        residual[h] -= demands[i]
    return placement


def build_case(
    app: AppGraph,
    topology: Topology,
    m: int,
    rho: float,
    seed: int,
) -> RealCase:
    rng = np.random.default_rng(seed)
    cost, degree, hosts = host_network(topology, m, rng)
    total = app.demands.sum(axis=0)
    share = np.maximum(degree, 1) / np.maximum(degree, 1).sum()
    capacities = np.outer(share, total / rho)
    placement = worst_fit_placement(app.demands, capacities, rng)
    instance = AssignmentInstance(app.interaction, app.demands, capacities, cost, name=f"{app.name}@{topology.name}")
    meta = {
        "app": app.name, "topology": topology.name, "m": m, "rho": rho, "seed": seed,
        "n": int(app.interaction.shape[0]), "hosts": hosts,
    }
    return RealCase(instance, placement, meta)


def build_case_with_retries(
    app: AppGraph,
    topologies: list[Topology],
    m: int,
    rho: float,
    seed: int,
    max_tries: int = 20,
) -> tuple[RealCase | None, int]:
    """Draw a topology and hosts; on worst-fit failure, redraw with the next seed.

    Returns the case (or None if every try failed) and the number of failed
    draws, which the experiments report per cell.
    """
    failures = 0
    for attempt in range(max_tries):
        draw_seed = seed + attempt
        rng = np.random.default_rng(draw_seed)
        topo = topologies[int(rng.integers(len(topologies)))]
        if len(topo.coords) < m:
            failures += 1
            continue
        try:
            case = build_case(app, topo, m, rho, draw_seed)
        except ValueError:
            failures += 1
            continue
        case.meta["construction_failures"] = failures
        return case, failures
    return None, failures


def load_workflow(npz_path: Path) -> AppGraph:
    data = np.load(npz_path)
    demands = data["demands"].astype(float).copy()
    if demands.shape[1] >= 2:
        demands[:, 1] /= 1e9   # bytes -> GB
    interaction = data["interaction"].astype(float) / 1e6  # bytes -> MB
    np.fill_diagonal(interaction, 0.0)
    return AppGraph(npz_path.stem, interaction, demands)


def load_microservice(json_path: Path) -> AppGraph:
    doc = json.loads(json_path.read_text())
    n = len(doc["nodes"])
    interaction = np.zeros((n, n))
    for a, b, v in doc["edges"]:
        interaction[int(a), int(b)] += float(v)
    demands = np.asarray(doc["demands"], dtype=float)
    demands[:, 1] /= 1024.0  # MB -> GB
    return AppGraph(doc["app"], interaction, demands)


def compose_tenants(apps: list[AppGraph], target_n: int, rng: np.random.Generator) -> AppGraph:
    chosen: list[AppGraph] = []
    while sum(a.interaction.shape[0] for a in chosen) < target_n:
        chosen.append(apps[int(rng.integers(len(apps)))])
    n = sum(a.interaction.shape[0] for a in chosen)
    interaction = np.zeros((n, n))
    offset = 0
    for a in chosen:
        k = a.interaction.shape[0]
        interaction[offset:offset + k, offset:offset + k] = a.interaction
        offset += k
    demands = np.vstack([a.demands for a in chosen])
    name = "tenants[" + "+".join(a.name for a in chosen) + "]"
    return AppGraph(name, interaction, demands)
