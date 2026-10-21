from certified_assignment.paper2_exact_selection import ValueItem, select_exact_expected_value


def test_exact_selector_obeys_budget_and_maximizes_value():
    items = [
        ValueItem("a", 5, 8.0),
        ValueItem("b", 4, 7.0),
        ValueItem("c", 6, 10.0),
    ]
    chosen = select_exact_expected_value(items, budget_bytes=10)
    assert set(chosen) == {"b", "c"}
    assert sum(next(i.size_bytes for i in items if i.key == k) for k in chosen) <= 10


def test_exact_selector_is_deterministic_under_ties():
    items = [ValueItem("b", 5, 1.0), ValueItem("a", 5, 1.0)]
    assert select_exact_expected_value(items, budget_bytes=5) == ("a",)
