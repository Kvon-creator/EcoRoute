"""Physical sanity checks for the explicitly hypothetical simulation."""
import numpy as np
import pytest
from scripts.simulate_fuel import PARAMETERS, assumed_speed, simulated_rate


def test_flat_road_units_and_energy_conversion():
    p = PARAMETERS
    speed = 36.0
    expected_force = (p['mass_kg'] * p['gravity_m_s2'] * p['rolling_coefficient']
                      + 0.5 * p['air_density_kg_m3'] * p['drag_area_m2'] * 10**2)
    expected = expected_force * 1000 / (p['drivetrain_efficiency'] * p['fuel_energy_j_per_liter']) + 0.9/36
    assert simulated_rate([[speed,0]])[0] == pytest.approx(expected)


def test_signed_grade_changes_consumption_without_negative_downhill_fuel():
    downhill, flat, uphill = simulated_rate([[40,-0.10],[40,0],[40,0.10]])
    assert 0 < downhill < flat < uphill
    assert downhill == pytest.approx(PARAMETERS['idle_liters_per_hour']/40)


@pytest.mark.parametrize('features', [[[0,0]], [[91,0]], [[40,0.26]], [[40,float('nan')]]])
def test_invalid_or_out_of_domain_inputs_are_rejected(features):
    with pytest.raises(ValueError):
        simulated_rate(features)


def test_speed_fallback_and_multiple_classifications_are_explicit():
    assert assumed_speed('unknown') == 30
    assert assumed_speed(['primary','residential']) == 30
    assert assumed_speed('service') == 20


def test_higher_mass_increases_uphill_fuel():
    heavier = dict(PARAMETERS, mass_kg=4000)
    assert simulated_rate([[40,0.10]], heavier)[0] > simulated_rate([[40,0.10]])[0]
