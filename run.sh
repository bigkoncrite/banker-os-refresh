#!/bin/bash
# Banker OS origination refresh. Usage: WORK=/path CH_API_KEY=... bash run.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; export WORK="${WORK:-$PWD}"; cd "$WORK"
pip install --break-system-packages -q pandas odfpy >/dev/null 2>&1 || true
python3 "$HERE/s1_fetch.py"
python3 "$HERE/s2_prep.py"
python3 "$HERE/s3_psc.py"
python3 "$HERE/s4_acc.py"
python3 "$HERE/s5_build.py" > build1.log
python3 "$HERE/s6_api.py" || echo "API stage skipped or failed" >> log.txt
python3 "$HERE/s5_build.py" > build2.log
python3 "$HERE/s7_publish.py"
rm -rf "$WORK/src/basic.zip" "$WORK/src/cqc.ods"
echo REFRESH_OK
