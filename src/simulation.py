"""Shared hypothetical fuel physics; independent of training and the dashboard."""
import numpy as np

PARAMETERS = dict(mass_kg=3000.0, rolling_coefficient=0.012,
                  drag_area_m2=1.1, air_density_kg_m3=1.2,
                  drivetrain_efficiency=0.25, fuel_energy_j_per_liter=34_200_000.0,
                  idle_liters_per_hour=0.9, gravity_m_s2=9.80665)


SPEEDS = dict(motorway=80, motorway_link=30, trunk=70, trunk_link=30,
              primary=60, primary_link=30, secondary=50, secondary_link=30,
              tertiary=40, tertiary_link=30, residential=30, living_street=15,
              service=20, unclassified=35)


def simulated_rate(features, parameters=None):
    """Steady-speed, non-regenerative hypothetical gasoline van; returns L/km.

    Grade is signed rise/run. Downhill braking dissipates excess energy.
    Idle allowance is added at all speeds, including downhill (no fuel cutoff).
    """
    p = PARAMETERS if parameters is None else parameters
    x = np.asarray(features, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2 or not np.isfinite(x).all():
        raise ValueError('Expected finite speed_kph,grade rows.')
    speed, grade = x.T
    if np.any((speed < 15) | (speed > 90) | (abs(grade) > 0.25)):
        raise ValueError('Simulation domain is 15-90 km/h and grades -0.25 to 0.25.')
    angle = np.arctan(grade)
    force = (p['mass_kg'] * p['gravity_m_s2'] *
             (p['rolling_coefficient'] * np.cos(angle) + np.sin(angle)) +
             0.5 * p['air_density_kg_m3'] * p['drag_area_m2'] * (speed / 3.6)**2)
    return (np.maximum(force, 0) * 1000 /
            (p['drivetrain_efficiency'] * p['fuel_energy_j_per_liter']) +
            p['idle_liters_per_hour'] / speed)


def assumed_speed(highway):
    kinds = highway if isinstance(highway, list) else [highway]
    # Multiple classifications use the conservative minimum; unknown defaults 30.
    return float(min(SPEEDS.get(str(kind), 30) for kind in kinds))
