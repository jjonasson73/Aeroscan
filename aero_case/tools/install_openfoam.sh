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

# timeout dödar bara sitt DIREKTA barn. add-debian-repo.sh körs som `curl ... | sudo bash`
# och startar i sin tur apt-get; slår tidsgränsen blir den apt-get:en föräldralös och
# fortsätter hålla /var/lib/apt/lists/lock. Nästa försök får då "Could not get lock" och
# alla omförsök faller på rad - en hängning blir en låskonflikt i stället.
#
# Därför väntar vi ut låset före varje försök i stället för att slå sönder det. Den
# föräldralösa processen gör färdigt sitt jobb och släpper låset av sig själv; att ta bort
# låsfilen under en körande apt är ett säkert sätt att få sönder paketdatabasen.
wait_apt() {
  local n=0
  while sudo fuser /var/lib/apt/lists/lock /var/lib/dpkg/lock-frontend \
                   /var/lib/dpkg/lock >/dev/null 2>&1; do
    n=$((n + 1))
    if [ "$n" -gt 60 ]; then
      echo "aptlåset släpptes inte på 5 minuter" >&2
      return 1
    fi
    [ "$n" = 1 ] && echo "väntar på att aptlåset ska släppas..."
    sleep 5
  done
  return 0
}

retry() {
  local what=$1; shift
  local n
  for n in 1 2 3 4; do
    wait_apt || return 1
    # -k 15: SIGKILL om kommandot inte dör på SIGTERM inom 15 s.
    # 600 s: apt-get update mot ett segt spegelarkiv tar legitimt flera minuter, och 300 s
    # var för snålt - det var den gränsen som utlöste låskonflikten ovan.
    if timeout -k 15 600 "$@"; then
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
