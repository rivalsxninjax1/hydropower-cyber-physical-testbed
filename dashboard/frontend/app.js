const RESERVOIR_INNER_TOP = 41;
const RESERVOIR_INNER_HEIGHT = 218;

const GATE_BASELINE_Y = 222;
const GATE_MAX_HEIGHT = 36;
const GATE_MIN_HEIGHT = 4;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss://" : "ws://";
  const ws = new WebSocket(protocol + location.host + "/ws/state");

  ws.onopen = () => setConnectionStatus("connected");
  ws.onclose = () => {
    setConnectionStatus("disconnected");
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    updateSchematic(state);
    updateReadouts(state);
    updateAlarmBanner(state);
  };
}

function setConnectionStatus(status) {
  const dot = document.getElementById("conn-dot");
  const label = document.getElementById("conn-label");
  dot.className = "dot dot-" + status;
  label.textContent = status === "connected" ? "LIVE" : "RECONNECTING…";
}

function updateSchematic(state) {
  const waterRect = document.getElementById("reservoir-water");
  const fillFraction = state.reservoir_level_pct / 100;
  const height = RESERVOIR_INNER_HEIGHT * fillFraction;
  const y = RESERVOIR_INNER_TOP + (RESERVOIR_INNER_HEIGHT - height);
  waterRect.setAttribute("y", y.toFixed(1));
  waterRect.setAttribute("height", height.toFixed(1));

  const gateBar = document.getElementById("gate-bar");
  const gateFraction = state.gate_position_pct / 100;
  const gateHeight = GATE_MIN_HEIGHT + gateFraction * GATE_MAX_HEIGHT;
  gateBar.setAttribute("height", gateHeight.toFixed(1));
  gateBar.setAttribute("y", (GATE_BASELINE_Y - gateHeight).toFixed(1));

  const flowLine = document.getElementById("penstock-flow");
  const flowDuration = clamp(6 - state.flow_m3s / 25, 0.4, 6);
  flowLine.style.animationDuration = flowDuration.toFixed(2) + "s";
  flowLine.style.opacity = state.flow_m3s > 0.5 ? "0.9" : "0.15";

  const turbineGroup = document.getElementById("turbine-group");
  const spinDuration = clamp(3 - (state.turbine_rpm / 1500) * 2.6, 0.25, 3);
  turbineGroup.style.animationDuration = spinDuration.toFixed(2) + "s";

  const breaker = document.getElementById("breaker-dot");
  breaker.style.fill = alarmColorVar(state.alarm_state);
}

function alarmColorVar(alarmState) {
  switch (alarmState) {
    case "WARNING": return "var(--accent-warning)";
    case "CRITICAL": return "var(--accent-critical)";
    default: return "var(--accent-normal)";
  }
}

function updateReadouts(state) {
  setText("val-level", state.reservoir_level_pct + "%  (" + state.reservoir_level_m + " m)");
  setText("val-inflow", state.inflow_m3s + " m3/s");
  setText("val-gate", state.gate_position_pct + "%  (target " + state.gate_target_pct + "%)");
  setText("val-flow", state.flow_m3s + " m3/s");
  setText("val-rpm", state.turbine_rpm + " RPM");
  setText("val-power", state.generator_power_mw + " MW");
  setText("val-freq", state.grid_frequency_hz + " Hz");
  setText("val-time", state.sim_time_s + " s");
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function updateAlarmBanner(state) {
  const banner = document.getElementById("alarm-banner");
  const text = document.getElementById("alarm-text");

  banner.className = "alarm-banner alarm-" + state.alarm_state.toLowerCase();

  const messages = {
    NORMAL: "NORMAL - plant operating within design limits",
    WARNING: "WARNING - turbine speed deviating from nominal",
    CRITICAL: "CRITICAL - abnormal plant state, investigate immediately"
  };
  text.textContent = messages[state.alarm_state] || state.alarm_state;
}

function setupGateControl() {
  const slider = document.getElementById("gate-slider");
  const sliderValue = document.getElementById("gate-slider-value");
  const button = document.getElementById("gate-set-btn");
  const status = document.getElementById("gate-set-status");

  slider.addEventListener("input", () => {
    sliderValue.textContent = slider.value + "%";
  });

  button.addEventListener("click", async () => {
    status.textContent = "Sending...";
    try {
      const response = await fetch("/api/gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_pct: Number(slider.value) })
      });
      if (!response.ok) throw new Error("Request failed");
      status.textContent = "Sent - watch the schematic respond.";
    } catch (err) {
      status.textContent = "Failed to send command.";
    }
    setTimeout(() => { status.textContent = ""; }, 4000);
  });
}

connect();
setupGateControl();
