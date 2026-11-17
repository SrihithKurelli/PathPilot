import pytest

from experiments.scenarios import (
    SCENARIO_NAMES, ImpairmentEvent, FlowSpec, Scenario, build_scenario, scenario_digest,
)


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_all_proposal_scenarios_are_deterministic_and_bounded(name):
    first = build_scenario(name, seed=19)
    second = build_scenario(name, seed=19)
    assert first == second
    assert first.duration_s > 0
    assert all(flow.start_offset_s + flow.duration_s <= first.duration_s
               for flow in first.flows)
    assert scenario_digest(first) == scenario_digest(second)


def test_mixed_short_long_contains_both_classes():
    scenario = build_scenario("mixed_short_long")
    classes = {flow.flow_class for flow in scenario.flows}
    assert classes == {"short", "long"}


def test_degradation_and_recovery_have_ordered_events():
    scenario = build_scenario("degrade_recover")
    assert [event.action for event in scenario.impairments] == ["set_rate", "set_rate"]
    assert scenario.impairments[0].offset_s < scenario.impairments[1].offset_s


def test_invalid_flow_and_impairment_rejected():
    with pytest.raises(ValueError):
        FlowSpec("SCTP", 10, 1, 0, "bad")
    with pytest.raises(ValueError):
        ImpairmentEvent(-1, "s1-s2-s4", "link_down")
    with pytest.raises(ValueError):
        Scenario("bad", 5, (FlowSpec("TCP", 10, 1, 0, "too_long"),))


def test_different_seeds_create_different_but_valid_workload_schedules():
    first = build_scenario("sudden_burst", seed=7)
    second = build_scenario("sudden_burst", seed=8)
    assert first != second
    assert scenario_digest(first) != scenario_digest(second)
    assert all(flow.start_offset_s + flow.duration_s <= first.duration_s
               for flow in first.flows)
