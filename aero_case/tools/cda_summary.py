"""Print the CdA breakdown as a markdown table for the Actions job summary.

    python tools/cda_summary.py [window]

Reads every postProcessing/CdA_*/<t>/coefficient.dat (whatever start time the run used,
not just 0) and reports the mean and spread over the last `window` iterations. A large
std relative to the mean means the run had not settled, so it is worth showing.
"""
import glob, pathlib, sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent.parent
window = int(sys.argv[1]) if len(sys.argv) > 1 else 150

files = sorted(glob.glob(str(HERE / 'postProcessing' / 'CdA_*' / '*' / 'coefficient.dat')))
if not files:
    print('_No coefficient.dat found - the solver did not produce force coefficients._')
    sys.exit(0)

print(f'| Del | CdA [m²] | std, sista {window} it | spridning | iterationer |')
print('|---|---|---|---|---|')
for f in files:
    name = pathlib.Path(f).parent.parent.name
    d = np.loadtxt(f, comments='#', ndmin=2)
    c = d[-window:, 1]          # column 1 = Cd (ESI v2312+ coefficient.dat layout)
    rel = abs(c.std() / c.mean()) if c.mean() else float('nan')
    print(f'| {name} | {c.mean():.4f} | {c.std():.4f} | {rel*100:.2f} % | {int(d[-1, 0])} |')
