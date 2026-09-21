#!/usr/bin/env bash
# Configure the case for one run. Shared by aero-cfd.yml and aero-delta.yml so the two
# workflows cannot drift apart -- a delta comparison is only meaningful if both sides were
# set up by exactly the same code.
#
#   tools/configure_case.sh <quick|coarse|medium|fine> <speed> <max_iterations> <nprocs> [fixed] [wide]
#
# A fifth argument "fixed" disables runTimeControl so the run goes to exactly max_iterations.
# A delta comparison needs both positions equally converged; letting the convergence monitor
# stop one at 700 iterations and the other at 1100 puts convergence noise straight into the
# difference you are trying to measure.
#
# A sixth argument "wide" widens the refinement boxes laterally. The yaw sweep passes it at
# EVERY angle, zero included: a mesh that changes with the angle would put mesh noise into
# the very trend the sweep is measuring.
set -euo pipefail
MESH=$1; U=$2; ITER=$3; NP=$4; FIXED=${5:-}; WIDE=${6:-}
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
# magUInf sitter i forceDefaults, som är en TOPPNIVÅ-post som de fyra function objects
# drar in med $forceDefaults. foamDictionary -set skriver om hela filen med makrot
# expanderat, så efter första skrivningen ovan (endTime) har var och en sin egen kopia och
# forceDefaults/magUInf når dem inte längre. Därför sätts den på varje function object,
# och vi läser tillbaka för att bevisa att den tog.
n_set=0
for fo in forceDefaults functions/CdA_total functions/CdA_rider functions/CdA_bike functions/CdA_wheels; do
  if foamDictionary -entry "$fo/magUInf" -set "$U" system/controlDict >/dev/null 2>&1; then
    n_set=$((n_set + 1))
  fi
done
got=$(foamDictionary -entry functions/CdA_total/magUInf -value system/controlDict 2>/dev/null | tr -d '[:space:];')
if [ "$got" != "$U" ]; then
  echo "magUInf sattes inte: CdA_total har '$got', ville ha '$U' (lyckades på $n_set ställen)" >&2
  exit 1
fi
echo "magUInf = $got satt på $n_set ställen i controlDict"

# --- orientation -------------------------------------------------------------------------
# build_model.py can turn the whole machine about the vertical axis (yaw_deg). The flow stays
# along +x so the wake keeps running down the long axis of the domain and the side patches
# stay valid symmetry planes; it is the bike that is turned into the wind.
#
# Four things have to turn with it, and every one of them is silent if it does not:
#   dragDir     drag is reported along the DIRECTION OF TRAVEL, not along the wind. Only the
#               travel-axis component costs watts -- a yawed rider carries a large side force
#               that does no work, and (1 0 0) would bill him for it.
#   pitchAxis   the moment reference frame follows the body.
#   wheel axis  the wheels still spin about their own axle.
#   origin      the axles have moved.
# These come from model_info.json rather than being duplicated here, and at yaw=0 they are
# exactly the values the case ships with, so this is a no-op for the straight-line runs.
read -r DDX DDY DDZ PAX PAY PAZ WAX WAY WAZ RX RY RZ FX FY FZ YAWDEG <<<"$(python3 -c "
import json
i = json.load(open('model_info.json'))
print(*i['drag_dir'], *i['pitch_axis'], *i['wheel_axis'],
      *i['axle_rear_m'], *i['axle_front_m'], i.get('yaw_deg', 0.0))")"
for fo in forceDefaults functions/CdA_total functions/CdA_rider functions/CdA_bike functions/CdA_wheels; do
  foamDictionary -entry "$fo/dragDir"   -set "($DDX $DDY $DDZ)" system/controlDict >/dev/null 2>&1 || true
  foamDictionary -entry "$fo/pitchAxis" -set "($PAX $PAY $PAZ)" system/controlDict >/dev/null 2>&1 || true
done
# Compare numerically: foamDictionary echoes 0 where model_info.json says 0.0, so a string
# comparison here would fail every single run.
got=$(foamDictionary -entry functions/CdA_total/dragDir -value system/controlDict | tr -d '();')
python3 -c "
import sys
got, want = [float(v) for v in sys.argv[1].split()], [float(v) for v in sys.argv[2].split()]
if max(abs(a - b) for a, b in zip(got, want)) > 1e-6:
    sys.exit(f'dragDir sattes inte: CdA_total har {got}, ville ha {want}')" \
  "$got" "$DDX $DDY $DDZ"

foamDictionary -entry boundaryField/wheel_rear/axis    -set "($WAX $WAY $WAZ)" 0/U
foamDictionary -entry boundaryField/wheel_front/axis   -set "($WAX $WAY $WAZ)" 0/U
foamDictionary -entry boundaryField/wheel_rear/origin  -set "($RX $RY $RZ)"    0/U
foamDictionary -entry boundaryField/wheel_front/origin -set "($FX $FY $FZ)"    0/U
echo "yaw = $YAWDEG grader | dragDir ($DDX $DDY $DDZ) = färdriktningen | hjulaxel ($WAX $WAY $WAZ)"


# Mesh resolution. foamDictionary edits the dictionary structure, so these cannot silently
# no-op the way a pattern-matching sed does when the file is reformatted.
if [ "$FIXED" = "fixed" ]; then
  foamDictionary -entry functions/stopWhenConverged/timeStart -set 1000000 system/controlDict
  echo "runTimeControl avstängd: kör till exakt $ITER iterationer"
fi

case "$MESH" in
  quick|coarse)
    for pat in rider bike wheel_rear wheel_front; do
      foamDictionary -entry "castellatedMeshControls/refinementSurfaces/$pat/level" -set "(4 5)" $S
    done
    foamDictionary -entry castellatedMeshControls/features -set \
      '({file "rider.eMesh"; level 5;} {file "bike.eMesh"; level 5;} {file "wheel_rear.eMesh"; level 5;} {file "wheel_front.eMesh"; level 5;})' $S
    foamDictionary -entry castellatedMeshControls/refinementRegions/nearBox/levels -set "((1E15 3))" $S
    foamDictionary -entry castellatedMeshControls/refinementRegions/wakeBox/levels -set "((1E15 2))" $S ;;
  medium)
    # fine's surface resolution with coarse's refinement boxes: coarse vs medium then differ
    # ONLY in how finely the body is resolved, which is what a refinement study needs.
    foamDictionary -entry castellatedMeshControls/refinementRegions/nearBox/levels -set "((1E15 3))" $S
    foamDictionary -entry castellatedMeshControls/refinementRegions/wakeBox/levels -set "((1E15 2))" $S ;;
  fine) : ;;   # the dictionary ships at fine
  *) echo "unknown mesh level: $MESH" >&2; exit 2 ;;
esac
# The refinement boxes are decided in one place, because two branches each setting them
# independently is how "quick" silently narrows the boxes the yaw sweep just widened.
NEAR_Y=0.5; WAKE_Y=0.8; WAKE_XMAX=4.5; WAKE_ZMAX=2.0
if [ "$MESH" = "quick" ]; then
  foamDictionary -entry addLayers -set false $S     # Spalding handles high y+
  WAKE_XMAX=2.5; WAKE_ZMAX=1.8                      # shorter wake box
fi
# A turned body must not poke out of its own refined region. At 20 deg the machine reaches
# y = +-0.41 m against a nearBox half-width of 0.50 m, too little refined air to trust on the
# windward side. The yaw sweep passes "wide" at every angle, zero included, so the mesh is the
# same at all of them and the trend is not measuring the mesh.
if [ "$WIDE" = "wide" ]; then NEAR_Y=0.7; WAKE_Y=1.1; fi
foamDictionary -entry geometry/nearBox/min -set "(-1.2 -$NEAR_Y 0)" $S
foamDictionary -entry geometry/nearBox/max -set "(1.6 $NEAR_Y 1.6)" $S
foamDictionary -entry geometry/wakeBox/min -set "(-1.5 -$WAKE_Y 0)" $S
foamDictionary -entry geometry/wakeBox/max -set "($WAKE_XMAX $WAKE_Y $WAKE_ZMAX)" $S

echo "--- effective configuration: mesh=$MESH U=$U iter=$ITER np=$NP ---"
echo "k = $TKE | omega_inlet = $TOMEGA | omega_wheel = $OMEGA rad/s"
for e in addLayers castellatedMeshControls/features \
         castellatedMeshControls/refinementSurfaces/rider/level \
         castellatedMeshControls/refinementRegions/nearBox/levels \
         castellatedMeshControls/refinementRegions/wakeBox/levels \
         geometry/nearBox/max geometry/wakeBox/max; do
  echo "$e = $(foamDictionary -entry "$e" -value $S | tr -d '\n')"
done
