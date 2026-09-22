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
# Kör ett kommando i EGEN PROCESSGRUPP med tidsgräns, och döda hela gruppen om den slår.
#
# timeout(1) signalerar bara sitt direkta barn. add-debian-repo.sh körs som
# `curl ... | sudo bash` och startar i sin tur apt-get; när tidsgränsen slog överlevde den
# apt-get:en och höll /var/lib/apt/lists/lock.
#
# Första försöket att laga det var att VÄNTA ut låset. Det var fel strategi: den
# föräldralösa apt-get:en satt fast på en stallad nedladdning och blev aldrig klar. Loggen
# visar det rakt av - wait_apt upptäckte låset korrekt och gav upp efter fem minuter. En
# process som är död i vattnet går inte att vänta ut, den måste dödas.
#
# ps i stället för kill -0 i väntesnurran: sudo kör apt som root, och kill -0 från
# runner-användaren mot en root-process ger EPERM, vilket hade tolkats som "processen är
# borta" och gjort snurran meningslös.
run_group() {
  local secs=$1; shift
  setsid "$@" &
  local pid=$! pgid n=0
  pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
  [ -n "$pgid" ] || pgid=$pid
  while ps -p "$pid" >/dev/null 2>&1; do
    n=$((n + 1))
    if [ "$n" -ge "$secs" ]; then
      echo "tidsgräns $secs s överskriden, dödar processgrupp $pgid" >&2
      sudo kill -TERM "-$pgid" 2>/dev/null || true
      sleep 5
      sudo kill -KILL "-$pgid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 1
  done
  wait "$pid"
}

retry() {
  local what=$1; shift
  local n
  for n in 1 2 3 4; do
    if run_group 600 "$@"; then
      [ "$n" -gt 1 ] && echo "$what lyckades på försök $n"
      return 0
    fi
    echo "$what misslyckades (försök $n av 4), väntar $((2**n)) s" >&2
    sleep $((2**n))
  done
  echo "$what gav upp efter 4 försök" >&2
  return 1
}

# Sprid ut starten. Åtta matrisjobb som alla hämtar från dl.openfoam.com i samma sekund är
# vad som stallar repot till att börja med - felet har aldrig dykt upp i en ensam körning.
STAGGER=$((RANDOM % 45))
echo "väntar $STAGGER s för att inte stampa på repot samtidigt som syskonjobben"
sleep "$STAGGER"

retry "apt-get update" sudo apt-get update -qq
retry "add-debian-repo" bash -c "curl -fsS --connect-timeout 20 --max-time 120 --retry 3 --retry-delay 5 https://dl.openfoam.com/add-debian-repo.sh | sudo bash"
retry "apt-get update (efter repo)" sudo apt-get update -qq
retry "apt-get install" sudo apt-get install -y --no-install-recommends "openfoam${VER}-default"

BASHRC="/usr/lib/openfoam/openfoam${VER}/etc/bashrc"
[ -f "$BASHRC" ] || { echo "OpenFOAM installerades men $BASHRC saknas" >&2; exit 1; }
echo "OF_BASHRC=$BASHRC" >> "$GITHUB_ENV"
echo "NP=$(nproc)" >> "$GITHUB_ENV"
echo "OpenFOAM $VER installerad, $(nproc) kärnor"
