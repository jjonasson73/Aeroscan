#!/usr/bin/env bash
# Configure the case for one run. Shared by aero-cfd.yml and aero-delta.yml so the two
# workflows cannot drift apart -- a delta comparison is only meaningful if both sides were
# set up by exactly the same code.
#
#   tools/configure_case.sh <quick|coarse|fine> <speed m/s> <max_iterations> <nprocs>
set -euo pipefail
MESH=$1; U=$2; ITER=$3; NP=$4
S=system/snappyHexMeshDict

foamDictionary -entry numberOfSubdomains -set "$NP"   system/decomposeParDict
foamDictionary -entry endTime            -set "$ITER" system/controlDict
foamDictionary -entry writeInterval      -set "$ITER" system/controlDict

# U, the turbulence inlet (k, omega) and the wheel rotation all follow from the one speed.
read -r OMEGA TKE TOMEGA <<<"$(python3 tools/inlet_conditions.py "$U")"
foamDictionary -entry Uinlet    -set "($U 0 0)" 0/include/initialConditions
foamDictionary -entry turbKE    -set "$TKE"     0/include/initialConditions
foamDictionary -entry turbOmega -set "$TOMEGA"  0/include/initialConditions
foamDictionary -entry boundaryField/wheel_rear/omega  -set "$OMEGA" 0/U
foamDictionary -entry boundaryField/wheel_front/omega -set "$OMEGA" 0/U
foamDictionary -entry functions/forceDefaults/magUInf -set "$U" system/controlDict

# Mesh resolution. foamDictionary edits the dictionary structure, so these cannot silently
# no-op the way a pattern-matching sed does when the file is reformatted.
case "$MESH" in
  quick|coarse)
    for pat in rider bike wheel_rear wheel_front; do
      foamDictionary -entry "castellatedMeshControls/refinementSurfaces/$pat/level" -set "(4 5)" $S
    done
    foamDictionary -entry castellatedMeshControls/features -set \
      '({file "rider.eMesh"; level 5;} {file "bike.eMesh"; level 5;} {file "wheel_rear.eMesh"; level 5;} {file "wheel_front.eMesh"; level 5;})' $S
    foamDictionary -entry castellatedMeshControls/refinementRegions/nearBox/levels -set "((1E15 3))" $S
    foamDictionary -entry castellatedMeshControls/refinementRegions/wakeBox/levels -set "((1E15 2))" $S ;;
  fine) : ;;   # the dictionary ships at fine
  *) echo "unknown mesh level: $MESH" >&2; exit 2 ;;
esac
if [ "$MESH" = "quick" ]; then
  foamDictionary -entry addLayers -set false $S                        # Spalding handles high y+
  foamDictionary -entry geometry/wakeBox/max -set "(2.5 0.7 1.8)" $S   # shorter wake box
fi

echo "--- effective configuration: mesh=$MESH U=$U iter=$ITER np=$NP ---"
echo "k = $TKE | omega_inlet = $TOMEGA | omega_wheel = $OMEGA rad/s"
for e in addLayers castellatedMeshControls/features \
         castellatedMeshControls/refinementSurfaces/rider/level \
         castellatedMeshControls/refinementRegions/nearBox/levels \
         castellatedMeshControls/refinementRegions/wakeBox/levels \
         geometry/wakeBox/max; do
  echo "$e = $(foamDictionary -entry "$e" -value $S | tr -d '\n')"
done
