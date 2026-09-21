#!/usr/bin/env bash
# Installera OpenFOAM på en CI-runner. Delad av aero-cfd, aero-delta och aero-yaw så att
# alla tre får samma härdning -- steget såg likadant ut på tre ställen och hängde sig på
# alla tre.
#
#   tools/install_openfoam.sh <of_version>
#
# Varför omförsök: startar man åtta matrisjobb samtidigt hämtar alla från dl.openfoam.com
# på en gång, och repot stallar under lasten. Utan tidsgräns blockerar apt i timmar i
# stället för att fela, och jobbet står kvar till workflow-timeouten (355 min) och bränner
# en runner hela tiden. Vi har sett exakt det: sju av åtta jobb klarade steget på ~75
# sekunder medan det åttonde stod i nästan två timmar.
#
# Steget självt ska dessutom ha `timeout-minutes` i workflow-filen. Det här skriptet
# skyddar mot ett stall i ett enskilt kommando; `timeout-minutes` skyddar mot allt annat.
set -euo pipefail
VER=$1

retry() {
  local what=$1; shift
  local n
  for n in 1 2 3 4; do
    if timeout 300 "$@"; then
      [ "$n" -gt 1 ] && echo "$what lyckades på försök $n"
      return 0
    fi
    echo "$what misslyckades (försök $n av 4), väntar $((2**n)) s" >&2
    sleep $((2**n))
  done
  echo "$what gav upp efter 4 försök" >&2
  return 1
}

retry "apt-get update" sudo apt-get update -qq
retry "add-debian-repo" bash -c "curl -fsS --connect-timeout 20 --max-time 120 --retry 3 --retry-delay 5 https://dl.openfoam.com/add-debian-repo.sh | sudo bash"
retry "apt-get update (efter repo)" sudo apt-get update -qq
retry "apt-get install" sudo apt-get install -y --no-install-recommends "openfoam${VER}-default"

BASHRC="/usr/lib/openfoam/openfoam${VER}/etc/bashrc"
[ -f "$BASHRC" ] || { echo "OpenFOAM installerades men $BASHRC saknas" >&2; exit 1; }
echo "OF_BASHRC=$BASHRC" >> "$GITHUB_ENV"
echo "NP=$(nproc)" >> "$GITHUB_ENV"
echo "OpenFOAM $VER installerad, $(nproc) kärnor"
