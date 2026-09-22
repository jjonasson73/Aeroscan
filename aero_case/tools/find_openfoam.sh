#!/usr/bin/env bash
# Hitta OpenFOAM-miljön i en container och verifiera att den duger till caset.
#
# Bilden opencfd/openfoam-default lägger inte nödvändigtvis bashrc där Debian-paketen gör
# det, och dess interna sökvägar går inte att inspektera utan att dra ner bilden. Därför
# LETAR vi i stället för att hårdkoda, och felar med en läsbar lista om inget hittas.
#
# Skriver OF_BASHRC och NP till GITHUB_ENV, precis som install_openfoam.sh gjorde.
set -euo pipefail

echo "--- letar efter OpenFOAM ---"
CAND=()
# Är miljön redan satt av bilden är det det säkraste svaret.
[ -n "${WM_PROJECT_DIR:-}" ] && CAND+=("$WM_PROJECT_DIR/etc/bashrc")
[ -n "${FOAM_ETC:-}" ] && CAND+=("$FOAM_ETC/bashrc")
# Annars de vanliga platserna, nyast först.
while IFS= read -r f; do CAND+=("$f"); done < <(
  ls -d /usr/lib/openfoam/openfoam*/etc/bashrc \
        /opt/openfoam*/etc/bashrc \
        /openfoam/etc/bashrc \
        /usr/local/openfoam*/etc/bashrc 2>/dev/null | sort -r)

OF_BASHRC=""
for c in "${CAND[@]:-}"; do
  if [ -n "$c" ] && [ -f "$c" ]; then OF_BASHRC="$c"; break; fi
done

if [ -z "$OF_BASHRC" ]; then
  echo "hittade ingen OpenFOAM-bashrc. Sökte på:" >&2
  printf '  %s\n' "${CAND[@]:-(inga kandidater)}" >&2
  echo "Det som finns under /usr/lib/openfoam, /opt och /openfoam:" >&2
  ls -la /usr/lib/openfoam /opt /openfoam 2>&1 | head -40 >&2
  exit 1
fi
echo "OF_BASHRC = $OF_BASHRC"

# Verifiera att verktygen caset faktiskt använder finns. En bild som saknar snappyHexMesh
# eller decomposePar går igenom installationen men faller långt senare, på ett fel som inte
# säger vad som är galet.
set +eu; # shellcheck disable=SC1090
source "$OF_BASHRC"; set -eu
MISSING=()
for app in blockMesh snappyHexMesh surfaceFeatureExtract decomposePar \
           potentialFoam simpleFoam checkMesh foamDictionary; do
  command -v "$app" >/dev/null 2>&1 || MISSING+=("$app")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "OpenFOAM hittad men dessa verktyg saknas: ${MISSING[*]}" >&2
  exit 1
fi
echo "alla åtta verktyg hittade"
echo "version: $(foamDictionary -help 2>&1 | head -1 || true)"
echo "WM_PROJECT_VERSION = ${WM_PROJECT_VERSION:-okänd}"

{
  echo "OF_BASHRC=$OF_BASHRC"
  echo "NP=$(nproc)"
  # OpenMPI vägrar köra som root utan de här. Containern kör som root, till skillnad från
  # runnern, så utan dem faller varje parallellsteg med ett meddelande om att det är farligt
  # att köra som root -- och inget om vad man ska göra åt det.
  echo "OMPI_ALLOW_RUN_AS_ROOT=1"
  echo "OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1"
} >> "$GITHUB_ENV"
echo "OpenFOAM ${WM_PROJECT_VERSION:-?} klar, $(nproc) kärnor"
