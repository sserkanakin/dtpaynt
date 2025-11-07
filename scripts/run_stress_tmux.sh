#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run the parallel stress test inside a tmux session and show
# monitors in separate panes so output doesn't interleave.
# Usage: from repo root:
#   HOST_RESULTS=/path/to/results DOCKER_RUN_ARGS='--cpus=12 --memory=90g' N_JOBS=10 TIMEOUT=3600 ./scripts/run_stress_tmux.sh

SESSION=${TMUX_SESSION:-dtpaynt-stress}
HOST_RESULTS=${HOST_RESULTS:-"$(pwd)/results"}
DOCKER_RUN_ARGS=${DOCKER_RUN_ARGS:-'--cpus=12 --memory=90g'}
N_JOBS=${N_JOBS:-10}
TIMEOUT=${TIMEOUT:-3600}

if ! command -v tmux >/dev/null 2>&1; then
  cat <<'MSG'
tmux is not installed or not available in PATH.

Recommended: install tmux and re-run this script. Example (Debian/Ubuntu):
  sudo apt update && sudo apt install -y tmux

Fallback (single-terminal): use the provided one-liner which runs monitors and tails logs
but note the output will interleave. Example:

  export HOST_RESULTS=/path/to/results \
         DOCKER_RUN_ARGS='--cpus=12 --memory=90g' \
         N_JOBS=10 TIMEOUT=3600 && \
  bash -c 'bash scripts/run_stress_test_parallel.sh & STRESS_PID=$!; \
    watch -n2 docker stats --no-stream & WATCH_PID=$!; \
    sleep 1; tail -F "$HOST_RESULTS"/logs/* 2>/dev/null & TAIL_PID=$!; \
    wait $STRESS_PID; kill $WATCH_PID $TAIL_PID 2>/dev/null || true'

MSG
  exit 1
fi

mkdir -p "${HOST_RESULTS}/logs"

echo "Starting tmux session '${SESSION}'..."

# Kill existing session if present to avoid duplicate names
if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Found existing tmux session '${SESSION}', killing it first..."
  tmux kill-session -t "${SESSION}"
fi

# Start session and run the stress script in pane 0
tmux new-session -d -s "${SESSION}" -n run
tmux send-keys -t "${SESSION}:0.0" \
  "export HOST_RESULTS='${HOST_RESULTS}'; export DOCKER_RUN_ARGS='${DOCKER_RUN_ARGS}'; export N_JOBS=${N_JOBS}; export TIMEOUT=${TIMEOUT}; bash scripts/run_stress_test_parallel.sh" C-m

# Right pane: docker stats for live container metrics (auto-refresh)
tmux split-window -h -t "${SESSION}:0.0"
tmux send-keys -t "${SESSION}:0.1" "watch -n2 -- 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"'" C-m

# Bottom pane: tail logs (join all logs if present)
tmux select-pane -t "${SESSION}:0.0"
tmux split-window -v -t "${SESSION}:0.0"
tmux send-keys -t "${SESSION}:0.2" "bash -lc 'sleep 1; tail -n +1 -F \"${HOST_RESULTS}/logs/*\" 2>/dev/null || true'" C-m

# Optional 4th pane: GPU monitor (if nvidia-smi exists)
if command -v nvidia-smi >/dev/null 2>&1; then
  tmux select-pane -t "${SESSION}:0.1"
  tmux split-window -v -t "${SESSION}:0.1"
  tmux send-keys -t "${SESSION}:0.3" "watch -n2 -- 'nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used --format=csv,noheader,nounits'" C-m
fi

tmux select-pane -t "${SESSION}:0.0"
echo "Attaching to tmux session '${SESSION}'. Use Ctrl-B % / - to rearrange panes, or Ctrl-B d to detach."
tmux attach-session -t "${SESSION}"
