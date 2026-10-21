from certified_assignment.paper2_external_eviction import ExternalEvictionOnlineStepPolicy
from certified_assignment.paper2_online_pilot import StoredCheckpoint


def rec(key, size, created, accessed):
    return StoredCheckpoint(
        key=(key,), blob=b"x", size_bytes=size, cumulative_pops=8,
        probability=0.0, expected_value=0.0,
        created_iteration=created, last_scored_iteration=accessed,
    )


def test_fifo_variable_size_evicts_oldest_until_incoming_fits():
    p = ExternalEvictionOnlineStepPolicy("fifo", slice_pops=8, budget_bytes=100)
    p.memory.records[(1,)] = rec(1, 60, 1, 9)
    p.memory.records[(2,)] = rec(2, 30, 2, 2)
    incoming = rec(3, 50, 3, 3)
    assert p._select_exact(incoming, 3)
    assert set(p.memory.records) == {(2,), (3,)}
    assert p.memory.bytes_used == 80
    assert p.memory.capacity_evictions == 1


def test_fifo_repeated_eviction_handles_heterogeneous_sizes():
    p = ExternalEvictionOnlineStepPolicy("fifo", slice_pops=8, budget_bytes=70)
    for i in range(1, 4):
        p.memory.records[(i,)] = rec(i, 30, i, i)
    incoming = rec(4, 60, 4, 4)
    assert p._select_exact(incoming, 4)
    assert set(p.memory.records) == {(4,)}
    assert p.memory.bytes_used == 60
    assert p.memory.capacity_evictions == 3


def test_lru_evicts_least_recently_accessed_not_oldest_created():
    p = ExternalEvictionOnlineStepPolicy("lru", slice_pops=8, budget_bytes=100)
    p.memory.records[(1,)] = rec(1, 40, 1, 20)   # old but recently hit
    p.memory.records[(2,)] = rec(2, 40, 2, 5)    # newer but least recent
    incoming = rec(3, 60, 3, 30)
    assert p._select_exact(incoming, 30)
    assert set(p.memory.records) == {(1,), (3,)}
    assert p.memory.capacity_evictions == 1


def test_lru_existing_hit_becomes_mru_on_reinsertion():
    p = ExternalEvictionOnlineStepPolicy("lru", slice_pops=8, budget_bytes=100)
    p.memory.records[(1,)] = rec(1, 40, 1, 4)
    p.memory.records[(2,)] = rec(2, 40, 2, 8)
    incoming = rec(1, 70, 1, 20)  # hit/update of key 1 at current iteration
    assert p._select_exact(incoming, 20)
    assert set(p.memory.records) == {(1,)}
    assert p.memory.records[(1,)].last_scored_iteration == 20
    assert p.memory.capacity_evictions == 1


def _random_kept(seed):
    p = ExternalEvictionOnlineStepPolicy("random", slice_pops=8, budget_bytes=90, eviction_seed=seed)
    for i in range(1, 5):
        p.memory.records[(i,)] = rec(i, 25, i, i)
    incoming = rec(5, 50, 5, 5)
    p._select_exact(incoming, 5)
    return tuple(sorted(p.memory.records)), p.memory.capacity_evictions


def test_random_replacement_is_seed_reproducible_and_budget_safe():
    a = _random_kept(77123)
    b = _random_kept(77123)
    assert a == b
    assert a[1] == 3
    assert (5,) in a[0]
