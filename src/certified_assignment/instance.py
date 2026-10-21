from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class AssignmentInstance:
    """A capacitated heterogeneous graph-assignment instance.

    The application graph may be directed. ``interaction[i, j]`` is the amount
    of communication from application node i to j. ``host_cost[k, l]`` is the
    cost of sending one unit of communication from host k to l.
    """

    interaction: np.ndarray
    demands: np.ndarray
    capacities: np.ndarray
    host_cost: np.ndarray
    name: str = "instance"

    def __post_init__(self) -> None:
        interaction = np.asarray(self.interaction, dtype=float)
        demands = np.asarray(self.demands, dtype=float)
        capacities = np.asarray(self.capacities, dtype=float)
        host_cost = np.asarray(self.host_cost, dtype=float)

        if interaction.ndim != 2 or interaction.shape[0] != interaction.shape[1]:
            raise ValueError("interaction must be a square matrix")
        n = interaction.shape[0]
        if demands.ndim != 2 or demands.shape[0] != n:
            raise ValueError("demands must have shape (n_nodes, n_resources)")
        if capacities.ndim != 2 or capacities.shape[1] != demands.shape[1]:
            raise ValueError("capacities must have shape (n_hosts, n_resources)")
        m = capacities.shape[0]
        if host_cost.shape != (m, m):
            raise ValueError("host_cost must have shape (n_hosts, n_hosts)")
        if np.any(~np.isfinite(interaction)) or np.any(interaction < 0):
            raise ValueError("interaction must be finite and non-negative")
        if np.any(~np.isfinite(demands)) or np.any(demands < 0):
            raise ValueError("demands must be finite and non-negative")
        if np.any(~np.isfinite(capacities)) or np.any(capacities < 0):
            raise ValueError("capacities must be finite and non-negative")
        if np.any(~np.isfinite(host_cost)) or np.any(host_cost < 0):
            raise ValueError("host_cost must be finite and non-negative")
        if np.any(np.diag(interaction) != 0):
            raise ValueError("interaction diagonal must be zero")

        object.__setattr__(self, "interaction", interaction)
        object.__setattr__(self, "demands", demands)
        object.__setattr__(self, "capacities", capacities)
        object.__setattr__(self, "host_cost", host_cost)

    @property
    def n_nodes(self) -> int:
        return int(self.interaction.shape[0])

    @property
    def n_hosts(self) -> int:
        return int(self.capacities.shape[0])

    @property
    def n_resources(self) -> int:
        return int(self.demands.shape[1])

    def validate_placement(self, placement: np.ndarray) -> np.ndarray:
        p = np.asarray(placement, dtype=int)
        if p.shape != (self.n_nodes,):
            raise ValueError(f"placement must have shape ({self.n_nodes},)")
        if np.any(p < 0) or np.any(p >= self.n_hosts):
            raise ValueError("placement contains an invalid host index")
        return p
