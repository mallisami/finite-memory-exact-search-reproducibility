from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import numpy as np

from .instance import AssignmentInstance

Domain = Literal["generic", "workflow", "microservice"]
DOMAINS: tuple[Domain, ...] = ("generic", "workflow", "microservice")


@dataclass(frozen=True)
class DomainCase:
    instance: AssignmentInstance
    placement: np.ndarray
    domain: str
    seed: int


def _balanced_placement(n: int, m: int, rng: np.random.Generator) -> np.ndarray:
    order = rng.permutation(n)
    placement = np.empty(n, dtype=int)
    placement[order] = np.arange(n) % m
    return placement


def _demands(n: int, rng: np.random.Generator) -> np.ndarray:
    cpu = np.clip(rng.lognormal(-0.5, 0.42, size=n), 0.12, 1.6)
    mem = np.clip(rng.lognormal(5.2, 0.52, size=n), 48.0, 768.0)
    return np.column_stack((cpu, mem))


def _capacities(demands: np.ndarray, placement: np.ndarray, m: int, headroom: float, rng: np.random.Generator) -> np.ndarray:
    usage = np.zeros((m, demands.shape[1]), dtype=float)
    for i, h in enumerate(placement):
        usage[h] += demands[i]
    spare = usage * rng.uniform(0.0, max(0.0, headroom - 1.0), size=(m, 1))
    return np.maximum(usage * headroom, usage + spare) + 1e-6


def _host_cost(m: int, rng: np.random.Generator, asymmetric: bool) -> np.ndarray:
    coordinates = rng.uniform(0.0, 25.0, size=(m, 2))
    base = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    if asymmetric:
        base *= rng.lognormal(0.0, 0.35, size=(m, m))
    else:
        base = 0.5 * (base + base.T)
    np.fill_diagonal(base, 0.0)
    return base


def _generic_interaction(n: int, rng: np.random.Generator) -> np.ndarray:
    density = min(0.35, 7.0 / np.sqrt(max(1, n)))
    weights = rng.gamma(1.4, 2.5, size=(n, n))
    weights *= rng.random((n, n)) < density
    np.fill_diagonal(weights, 0.0)
    return weights


def _workflow_interaction(n: int, rng: np.random.Generator) -> np.ndarray:
    n_layers = max(4, int(round(np.sqrt(n))))
    layer = np.floor(np.linspace(0, n_layers, n, endpoint=False)).astype(int)
    rng.shuffle(layer)
    weights = np.zeros((n, n), dtype=float)
    for i in range(n):
        later = np.flatnonzero((layer > layer[i]) & (layer <= layer[i] + 2))
        if later.size == 0:
            continue
        count = min(later.size, int(rng.integers(1, min(5, later.size) + 1)))
        targets = rng.choice(later, size=count, replace=False)
        for j in targets:
            distance = max(1, int(layer[j] - layer[i]))
            weights[i, j] += rng.gamma(2.0, 6.0 / distance)
    # Sparse feedback/control edges make the graph directed but not a pure chain.
    feedback = rng.random((n, n)) < (0.01 + 1.0 / max(200.0, n * n))
    weights += feedback * rng.gamma(1.2, 1.0, size=(n, n))
    np.fill_diagonal(weights, 0.0)
    return weights


def _microservice_interaction(n: int, rng: np.random.Generator) -> np.ndarray:
    communities = max(3, int(round(np.sqrt(n / 2))))
    labels = np.arange(n) % communities
    rng.shuffle(labels)
    weights = rng.gamma(1.1, 0.15, size=(n, n))
    same = labels[:, None] == labels[None, :]
    weights += same * rng.gamma(2.0, 4.5, size=(n, n))
    gateways = np.arange(min(3, n))
    for gateway in gateways:
        targets = rng.choice(np.arange(n), size=min(n, max(4, n // 4)), replace=False)
        weights[gateway, targets] += rng.gamma(2.0, 5.0, size=targets.size)
        weights[targets, gateway] += rng.gamma(1.5, 2.0, size=targets.size)
    # Database-like strongly coupled service pairs.
    remaining = np.arange(len(gateways), n)
    rng.shuffle(remaining)
    for a, b in zip(remaining[::2], remaining[1::2]):
        weights[a, b] += rng.uniform(15.0, 35.0)
        weights[b, a] += rng.uniform(4.0, 12.0)
    np.fill_diagonal(weights, 0.0)
    return weights


def make_domain_case(domain: Domain, n: int, m: int, seed: int) -> DomainCase:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain: {domain}")
    if n < m or m < 2:
        raise ValueError("require n >= m >= 2")
    rng = np.random.default_rng(seed)
    placement = _balanced_placement(n, m, rng)
    demands = _demands(n, rng)

    if domain == "generic":
        interaction = _generic_interaction(n, rng)
        asymmetric = True
        headroom = 1.14
    elif domain == "workflow":
        interaction = _workflow_interaction(n, rng)
        asymmetric = True
        headroom = 1.12
    else:
        interaction = _microservice_interaction(n, rng)
        asymmetric = False
        headroom = 1.10

    host_cost = _host_cost(m, rng, asymmetric=asymmetric)
    capacities = _capacities(demands, placement, m, headroom, rng)
    instance = AssignmentInstance(
        interaction=interaction,
        demands=demands,
        capacities=capacities,
        host_cost=host_cost,
        name=f"{domain}_n{n}_m{m}_s{seed}",
    )
    return DomainCase(instance, placement, domain, seed)
