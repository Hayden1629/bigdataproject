#!/bin/bash
# overnight-claude.sh
# Started at 10:52 PM. Schedule:
#   Phase 1: Run now until rate limited
#   Phase 2: Restart at ~2:07 AM (3h15m from now) when short-term resets
#   Phase 3+: Keep restarting on short-term resets until 11:00 AM
#
# Usage: ./overnight-claude.sh /path/to/project "Your task prompt here"

set -euo pipefail

PROJECT_DIR="${1:?Usage: $0 <project-dir> <prompt>}"
PROMPT="${2:?Usage: $0 <project-dir> <prompt>}"
DEADLINE="$(date -d 'tomorrow 11:00' +%s 2>/dev/null || date -j -v+1d -v11H -v0M -v0S +%s)"
SHORT_TERM_RESET=11700  # 3h15m in seconds
LOG_DIR="$PROJECT_DIR/.claude-overnight"
POLL_INTERVAL=60        # seconds between rate-limit retries
MAX_CONSECUTIVE_FAILS=5 # give up on a phase after this many back-to-back failures

mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOGFILE"; }

past_deadline() { [ "$(date +%s)" -ge "$DEADLINE" ]; }

# Run a single Claude session until it finishes or gets rate limited.
# Returns 0 on clean finish, 1 on rate limit, 2 on other error.
run_session() {
    local phase="$1"
    local session_log="$LOG_DIR/session-${phase}-$(date +%H%M%S).log"

    log "=== Phase $phase: starting session ==="

    claude -p "$PROMPT" \
        --dangerously-skip-permissions \
        --continue \
        --output-format json \
        > "$session_log" 2>&1
    local rc=$?

    if grep -qi "rate.limit\|overloaded\|too many\|529\|429\|quota\|capacity" "$session_log" 2>/dev/null; then
        log "Phase $phase: hit rate limit."
        return 1
    fi

    if [ $rc -ne 0 ]; then
        log "Phase $phase: exited with code $rc (non-rate-limit error)."
        return 2
    fi

    log "Phase $phase: completed cleanly."
    return 0
}

# Keep retrying a session until it finishes or we hit too many non-rate-limit errors.
burn_quota() {
    local phase="$1"
    local consecutive_fails=0

    while ! past_deadline; do
        run_session "$phase"
        local result=$?

        case $result in
            0) # clean finish
                log "Phase $phase: task completed. Moving on."
                return 0
                ;;
            1) # rate limited - this phase is done
                log "Phase $phase: quota exhausted."
                return 1
                ;;
            2) # other error
                consecutive_fails=$((consecutive_fails + 1))
                if [ $consecutive_fails -ge $MAX_CONSECUTIVE_FAILS ]; then
                    log "Phase $phase: $MAX_CONSECUTIVE_FAILS consecutive failures. Giving up on this phase."
                    return 2
                fi
                log "Phase $phase: retrying in ${POLL_INTERVAL}s ($consecutive_fails/$MAX_CONSECUTIVE_FAILS)..."
                sleep $POLL_INTERVAL
                ;;
        esac
    done

    log "Phase $phase: hit 11 AM deadline."
    return 0
}

# ---------------------------------------------------------------------------

cd "$PROJECT_DIR"
log "Project: $PROJECT_DIR"
log "Deadline: $(date -d "@$DEADLINE" 2>/dev/null || date -r "$DEADLINE")"
log "Prompt: $PROMPT"
log ""

# --- Phase 1: burn current quota ---
phase=1
burn_quota $phase

if past_deadline; then log "Done (deadline reached)."; exit 0; fi

# --- Sleep until first short-term reset (~2:07 AM) ---
now=$(date +%s)
first_reset=$((now + SHORT_TERM_RESET))
if [ "$first_reset" -ge "$DEADLINE" ]; then
    log "First reset would be past deadline. Done."
    exit 0
fi

sleep_secs=$((first_reset - $(date +%s)))
log "Sleeping ${sleep_secs}s until short-term reset (~$(date -d "+${sleep_secs} seconds" '+%H:%M' 2>/dev/null || date -v+${sleep_secs}S '+%H:%M'))..."
sleep "$sleep_secs"

# --- Phase 2+: loop on short-term resets until 11 AM ---
phase=2
while ! past_deadline; do
    log ""
    burn_quota $phase
    phase=$((phase + 1))

    if past_deadline; then break; fi

    # Wait for next short-term reset
    sleep_secs=$SHORT_TERM_RESET
    wake_time=$(( $(date +%s) + sleep_secs ))
    if [ "$wake_time" -ge "$DEADLINE" ]; then
        # Not enough time for another full cycle - sleep until deadline and do one last push
        sleep_secs=$(( DEADLINE - $(date +%s) ))
        if [ "$sleep_secs" -le 0 ]; then break; fi
        log "Next reset would be past deadline. Sleeping ${sleep_secs}s for final push..."
        sleep "$sleep_secs"
        burn_quota $phase
        break
    fi

    log "Sleeping ${sleep_secs}s until next short-term reset (~$(date -d "+${sleep_secs} seconds" '+%H:%M' 2>/dev/null || date -v+${sleep_secs}S '+%H:%M'))..."
    sleep "$sleep_secs"
done

log ""
log "=== Overnight run complete. $((phase - 1)) phases executed. ==="
log "Logs: $LOG_DIR"