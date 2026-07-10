#!/usr/bin/env bash
# Regression tests for scripts/scan-cli-hygiene.sh — mktemp sandbox.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN="$(cd "$SCRIPT_DIR/.." && pwd)/scripts/scan-cli-hygiene.sh"

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0
ok()   { echo "ok - $1"; pass=$((pass+1)); }
bad()  { echo "FAIL - $1"; echo "  $2"; fail=$((fail+1)); }
has()  { [[ "$1" == *"$2"* ]] && ok "$3" || bad "$3" "wanted: $2 | got: $1"; }
hasnt(){ [[ "$1" != *"$2"* ]] && ok "$3" || bad "$3" "unwanted: $2"; }

# --- clean tree -----------------------------------------------------------------
mkdir -p "$tmp/clean"
printf 'print("hello ascii")\n' > "$tmp/clean/ok.py"
out="$(bash "$SCAN" "$tmp/clean")"
has "$out" "no hazards found" "clean source reports nothing"

# --- NON_ASCII_OUTPUT -----------------------------------------------------------
proj="$tmp/proj"; mkdir -p "$proj"
printf 'print("done \xe2\x80\x94 ok")\n' > "$proj/emdash.py"   # em-dash in a print
printf 'x = "internal \xe2\x86\x92 not printed"\n' > "$proj/silent.py"  # arrow, NOT a sink
out="$(bash "$SCAN" "$proj")"
has "$out" "emdash.py:1: NON_ASCII_OUTPUT" "non-ASCII in print flagged"
hasnt "$out" "silent.py" "non-ASCII in a non-output string not flagged"

# --- PYTHON3_HARDCODE -----------------------------------------------------------
printf 'import subprocess\nsubprocess.run(["python3", "-c", "pass"])\n' > "$proj/hard.py"
out="$(bash "$SCAN" "$proj")"
has "$out" "hard.py:2: PYTHON3_HARDCODE" "hardcoded python3 flagged"

# --- HEREDOC_BACKSLASH ----------------------------------------------------------
cat > "$proj/hd.sh" <<'OUTER'
#!/usr/bin/env bash
cat <<EOF
line one\nline two
EOF
OUTER
out="$(bash "$SCAN" "$proj")"
has "$out" "HEREDOC_BACKSLASH" "escaped \\n inside heredoc flagged"

# --- SET_E_HOOK (only in hooks/) ------------------------------------------------
mkdir -p "$proj/hooks"
printf '#!/usr/bin/env bash\nset -e\necho hi\n' > "$proj/hooks/h.sh"
printf '#!/usr/bin/env bash\nset -e\necho hi\n' > "$proj/notahook.sh"
out="$(bash "$SCAN" "$proj")"
has "$out" "hooks/h.sh:2: SET_E_HOOK" "set -e in hooks/ flagged"
hasnt "$out" "notahook.sh" "set -e outside hooks/ not flagged"
# set -euo pipefail must NOT trip the bare-set-e rule
printf '#!/usr/bin/env bash\nset -euo pipefail\n' > "$proj/hooks/safe.sh"
out="$(bash "$SCAN" "$proj/hooks/safe.sh")"
hasnt "$out" "SET_E_HOOK" "set -euo pipefail is not flagged"

# --- CMD_SPAWN ------------------------------------------------------------------
printf "const {spawn} = require('child_process');\nspawn('anvil.cmd', ['x']);\n" > "$proj/run.js"
out="$(bash "$SCAN" "$proj")"
has "$out" "run.js:2: CMD_SPAWN" ".cmd spawn from Node flagged"

# --- HEREDOC state machine: bare-word body line must NOT reset (review #1) ----
cat > "$proj/hd_bareword.sh" <<'OUTER'
#!/usr/bin/env bash
cat <<EOF
foo
later\nescape
EOF
OUTER
out="$(bash "$SCAN" "$proj/hd_bareword.sh")"
has "$out" "hd_bareword.sh:4: HEREDOC_BACKSLASH" "bare-word body line does not end the heredoc early"

# --- HEREDOC with a DIGIT delimiter must reset (review #2) ---------------------
cat > "$proj/hd_digit.sh" <<'OUTER'
#!/usr/bin/env bash
cat <<'EOF2'
body\nwith escape
EOF2
echo "print(x)"
OUTER
out="$(bash "$SCAN" "$proj/hd_digit.sh")"
has "$out" "hd_digit.sh:3: HEREDOC_BACKSLASH" "digit-delimiter heredoc body flagged"
hasnt "$out" "hd_digit.sh:5" "digit delimiter resets — line after heredoc not falsely flagged"

# --- HEREDOC_BACKSLASH only inside a heredoc, not in normal code ---------------
printf '#!/usr/bin/env bash\nprintf "a\\\\nb"\n' > "$proj/notinhd.sh"
out="$(bash "$SCAN" "$proj/notinhd.sh")"
hasnt "$out" "notinhd.sh" "escaped backslash OUTSIDE a heredoc is not HEREDOC_BACKSLASH"

# --- CRLF file: pure-ASCII print line is NOT flagged NON_ASCII (review #3) -----
printf 'print("hello ascii")\r\nx = 1\r\n' > "$proj/crlf.py"
out="$(bash "$SCAN" "$proj/crlf.py")"
hasnt "$out" "crlf.py:1: NON_ASCII_OUTPUT" "CRLF line ending does not read as a non-ASCII byte"

# --- explicit self-arg is skipped (review #4) ---------------------------------
out="$(bash "$SCAN" "$SCAN")"
has "$out" "no hazards found" "scanner passed as an explicit arg excludes itself"

# --- --json shape + always exit 0 ----------------------------------------------
out="$(bash "$SCAN" "$proj" --json)"; rc=$?
[[ "$rc" == "0" ]] && ok "advisory exit 0" || bad "exit code" "got $rc"
has "$out" '"rule":"NON_ASCII_OUTPUT"' "json carries rule"
has "$out" '"count":' "json carries count"
# valid JSON (python parse)
if python3 -c "import json,sys;json.load(sys.stdin)" <<<"$out" 2>/dev/null; then
  ok "json parses"; else bad "json parses" "invalid: $out"; fi

echo
echo "passed=$pass failed=$fail"
[[ $fail -eq 0 ]]
