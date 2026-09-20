"""Derive every speed-dependent case value from one speed.

    python tools/inlet_conditions.py 12.5      ->  omega_wheel k omega_inlet

Turbulence intensity I = 1 %, length scale L = 0.1 m, Cmu = 0.09.
The tyre radius comes from model_info.json so it can never drift from the geometry.
"""
import json, math, pathlib, sys

I, LT, CMU = 0.01, 0.1, 0.09
HERE = pathlib.Path(__file__).resolve().parent.parent


def conditions(u, radius):
    k = 1.5 * (u * I) ** 2
    return u / radius, k, math.sqrt(k) / (CMU ** 0.25 * LT)


if __name__ == '__main__':
    u = float(sys.argv[1])
    r = json.load(open(HERE / 'model_info.json'))['wheel_radius_m']
    omega_wheel, k, omega_inlet = conditions(u, r)
    print(round(omega_wheel, 3), round(k, 6), round(omega_inlet, 4))
