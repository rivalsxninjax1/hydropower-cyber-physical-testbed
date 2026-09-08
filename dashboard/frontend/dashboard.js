// Dashboard landing page: polls /api/state for the plant summary
// tiles and /api/ids-alerts for the security summary tile. Simple
// fetch polling rather than a WebSocket, since this page only needs
// periodic snapshots, not smooth real-time animation like Plant View.

const POLL_MS = 3000;

function setConnectionStatus(status) {
  const dot = document.getElementById("conn-dot");
  const label = document.getElementById("conn-label");
  dot.className = "dot dot-" + status;
  label.textContent = status === "connected" ? "LIVE" : "DISCONNECTED";
}

async function refreshPlantTiles() {
  try {
    const response = await fetch("/api/state");
    const state = await response.json();

    if (!state.plc_connected) {
      setConnectionStatus("disconnected");
      document.getElementById("tile-alarm-state").textContent = "OFFLINE";
      document.getElementById("tile-alarm-sub").textContent = "PLC unreachable";
      return;
    }

    setConnectionStatus("connected");

    const alarmTile = document.getElementById("tile-alarm-state");
    alarmTile.textContent = state.alarm_state;
    alarmTile.className = "overview-tile-value overview-tile-value-" + state.alarm_state.toLowerCase();
    document.getElementById("tile-alarm-sub").textContent =
      "Poll latency: " + state.poll_latency_ms + " ms";

    document.getElementById("tile-level").textContent = state.reservoir_level_pct + "%";
    document.getElementById("tile-gate-sub").textContent =
      "Gate " + state.gate_position_pct + "% (target " + state.gate_target_pct + "%)";

    document.getElementById("tile-power").textContent = state.generator_power_mw + " MW";
    document.getElementById("tile-power-sub").textContent =
      "Flow " + state.flow_m3s + " m3/s, " + state.turbine_rpm + " RPM";
  } catch (err) {
    setConnectionStatus("disconnected");
  }
}

async function refreshSecurityTile() {
  try {
    const response = await fetch("/api/ids-alerts?limit=20");
    const alerts = await response.json();

    const tile = document.getElementById("tile-security");
    const sub = document.getElementById("tile-security-sub");

    if (alerts.length === 0) {
      tile.textContent = "0 Alerts";
      tile.className = "overview-tile-value overview-tile-value-normal";
      sub.textContent = "No IDS alerts recorded yet";
      return;
    }

    const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;
    tile.textContent = alerts.length + " Alert" + (alerts.length === 1 ? "" : "s");
    tile.className = "overview-tile-value overview-tile-value-" +
      (criticalCount > 0 ? "critical" : "warning");
    sub.textContent = "Most recent: " + alerts[0].rule + " (" + alerts[0].severity + ")";
  } catch (err) {
    document.getElementById("tile-security-sub").textContent = "Could not reach backend.";
  }
}

function refreshAll() {
  refreshPlantTiles();
  refreshSecurityTile();
}

refreshAll();
setInterval(refreshAll, POLL_MS);