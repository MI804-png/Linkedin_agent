// popup.js — LinkedIn AutoApply Chrome Extension

const DEFAULT_SERVER = "https://linkedin-autoapply.onrender.com";

// ── Helpers ────────────────────────────────────────────────────────────────

function $(id) { return document.getElementById(id); }

async function getStorage(keys) {
  return new Promise(r => chrome.storage.local.get(keys, r));
}
async function setStorage(obj) {
  return new Promise(r => chrome.storage.local.set(obj, r));
}

function showView(name) {
  ["login", "dashboard", "running"].forEach(v => {
    const el = $(`view-${v}`);
    if (el) el.style.display = v === name ? "block" : "none";
  });
}

function formatNextRun(isoString) {
  if (!isoString) return "Not scheduled";
  const d = new Date(isoString);
  return d.toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

// ── API calls ──────────────────────────────────────────────────────────────

async function apiLogin(server, email, password) {
  const r = await fetch(`${server}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!r.ok) throw new Error((await r.json()).error || "Login failed");
  return r.json(); // { token, user_id }
}

async function apiStatus(server, token) {
  const r = await fetch(`${server}/api/ext/status`, {
    headers: { "Authorization": `Bearer ${token}` }
  });
  if (!r.ok) throw new Error("Session expired");
  return r.json(); // { today, total, auto_apply_enabled, next_run }
}

async function apiSetAuto(server, token, enabled) {
  const r = await fetch(`${server}/api/ext/set_auto`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    body: JSON.stringify({ enabled })
  });
  if (!r.ok) throw new Error("Failed to update");
  return r.json();
}

// ── Init ──────────────────────────────────────────────────────────────────

async function init() {
  const { token, server, user_id, running } = await getStorage(["token", "server", "user_id", "running"]);
  const serverUrl = server || DEFAULT_SERVER;
  $("server-url").value = serverUrl;

  if (running) {
    showView("running");
    pollRunStatus();
    return;
  }

  if (!token) {
    showView("login");
    return;
  }

  try {
    const status = await apiStatus(serverUrl, token);
    $("stat-today").textContent = status.today ?? "0";
    $("stat-total").textContent = status.total ?? "0";
    $("toggle-auto").checked = !!status.auto_apply_enabled;
    $("next-run-info").textContent = "Next run: " + formatNextRun(status.next_run);
    showView("dashboard");
  } catch {
    await setStorage({ token: null });
    showView("login");
  }
}

// ── Login ─────────────────────────────────────────────────────────────────

$("btn-save-server").addEventListener("click", async () => {
  const url = $("server-url").value.trim().replace(/\/$/, "");
  if (url) await setStorage({ server: url });
});

$("btn-login").addEventListener("click", async () => {
  const server = ($("server-url").value.trim().replace(/\/$/, "")) || DEFAULT_SERVER;
  const email = $("login-email").value.trim();
  const password = $("login-password").value;
  $("login-error").textContent = "";

  if (!email || !password) {
    $("login-error").textContent = "Enter your email and password.";
    return;
  }

  const btn = $("btn-login");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Connecting…';

  try {
    const { token, user_id } = await apiLogin(server, email, password);
    await setStorage({ token, user_id, server });
    await init();
  } catch (e) {
    $("login-error").textContent = e.message;
    btn.disabled = false;
    btn.textContent = "Connect Account";
  }
});

// ── Dashboard ─────────────────────────────────────────────────────────────

$("toggle-auto").addEventListener("change", async () => {
  const { token, server } = await getStorage(["token", "server"]);
  const serverUrl = server || DEFAULT_SERVER;
  const enabled = $("toggle-auto").checked;
  try {
    await apiSetAuto(serverUrl, token, enabled);
    // Tell background to schedule/cancel alarm
    chrome.runtime.sendMessage({ type: "SET_AUTO", enabled });
    $("next-run-info").textContent = enabled
      ? "Next run: tomorrow 08:30"
      : "Next run: not scheduled";
  } catch (e) {
    $("toggle-auto").checked = !enabled; // revert
  }
});

$("btn-run-now").addEventListener("click", async () => {
  await setStorage({ running: true });
  chrome.runtime.sendMessage({ type: "RUN_NOW" });
  showView("running");
  $("run-log").textContent = "Opening LinkedIn…\n";
  pollRunStatus();
});

$("btn-open-dashboard").addEventListener("click", async () => {
  const { server } = await getStorage(["server"]);
  chrome.tabs.create({ url: (server || DEFAULT_SERVER) + "/dashboard" });
});

$("btn-logout").addEventListener("click", async () => {
  await setStorage({ token: null, user_id: null, running: false });
  showView("login");
});

// ── Running view ──────────────────────────────────────────────────────────

$("btn-stop").addEventListener("click", async () => {
  chrome.runtime.sendMessage({ type: "STOP_RUN" });
  await setStorage({ running: false });
  showView("dashboard");
});

let pollInterval = null;

function pollRunStatus() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    const { running, run_log } = await getStorage(["running", "run_log"]);
    if (run_log) {
      $("run-log").textContent = run_log;
      $("run-log").scrollTop = $("run-log").scrollHeight;
    }
    if (!running) {
      clearInterval(pollInterval);
      await init();
    }
  }, 1500);
}

// ── Boot ──────────────────────────────────────────────────────────────────

init();
