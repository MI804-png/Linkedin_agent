// background.js — Service Worker for LinkedIn AutoApply
// Handles: alarms, tab management, messaging with popup + content script

const DEFAULT_SERVER = "http://localhost:5000";
const ALARM_NAME = "daily_apply";
const LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/";

// ── Storage helpers ────────────────────────────────────────────────────────

function getStorage(keys) {
  return new Promise(r => chrome.storage.local.get(keys, r));
}
function setStorage(obj) {
  return new Promise(r => chrome.storage.local.set(obj, r));
}

// ── Alarm scheduling ──────────────────────────────────────────────────────

function scheduleDaily() {
  chrome.alarms.clear(ALARM_NAME, () => {
    // Fire every day at 08:30 local time
    const now = new Date();
    const next = new Date();
    next.setHours(8, 30, 0, 0);
    if (next <= now) next.setDate(next.getDate() + 1);
    const delayMs = next.getTime() - now.getTime();
    chrome.alarms.create(ALARM_NAME, {
      delayInMinutes: Math.ceil(delayMs / 60000),
      periodInMinutes: 24 * 60
    });
    console.log("[AutoApply] Next run scheduled for", next.toLocaleString());
  });
}

function cancelDaily() {
  chrome.alarms.clear(ALARM_NAME);
}

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === ALARM_NAME) {
    startRun();
  }
});

// ── Run logic ─────────────────────────────────────────────────────────────

let activeTabId = null;
let runAborted = false;

async function startRun() {
  const { token, server } = await getStorage(["token", "server"]);
  if (!token) {
    appendLog("Not connected — open extension popup to log in.");
    return;
  }

  runAborted = false;
  await setStorage({ running: true, run_log: "" });
  appendLog("Starting LinkedIn AutoApply…\n");

  // Fetch config from server
  let config;
  try {
    const serverUrl = server || DEFAULT_SERVER;
    const r = await fetch(`${serverUrl}/api/ext/config`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!r.ok) throw new Error("Auth failed");
    config = await r.json();
  } catch (e) {
    appendLog("Failed to fetch config: " + e.message);
    await finishRun({ error: e.message });
    return;
  }

  appendLog(`Config loaded. Keywords: ${config.keywords.join(", ")}`);
  appendLog(`Locations: ${config.locations.join(", ")}`);
  appendLog(`Limit: ${config.max_applications} applications\n`);

  const stats = { scanned: 0, submitted: 0, skipped: 0, failures: 0 };

  for (const keyword of config.keywords) {
    for (const location of config.locations) {
      if (runAborted) break;
      if (stats.submitted >= config.max_applications) break;
      await processSearch(keyword, location, config, stats);
    }
    if (runAborted || stats.submitted >= config.max_applications) break;
  }

  appendLog(`\nDone. Applied: ${stats.submitted}, Skipped: ${stats.skipped}, Failures: ${stats.failures}`);
  await finishRun(stats);
}

async function processSearch(keyword, location, config, stats) {
  appendLog(`\nSearching: "${keyword}" in ${location}…`);

  const encoded_keyword = encodeURIComponent(keyword);
  const encoded_location = encodeURIComponent(location);
  const days = config.posted_days_ago || 7;
  const searchUrl = `https://www.linkedin.com/jobs/search/?keywords=${encoded_keyword}&location=${encoded_location}&f_LF=f_AL&f_TPR=r${days * 86400}&sortBy=DD`;

  // Open or reuse tab
  const tab = await openTab(searchUrl);
  if (!tab) return;
  activeTabId = tab.id;

  await sleep(3000);

  // Get job URLs from search results
  let jobUrls = [];
  try {
    const result = await chrome.scripting.executeScript({
      target: { tabId: activeTabId },
      func: extractJobUrls
    });
    jobUrls = result[0]?.result || [];
  } catch (e) {
    appendLog("Failed to extract jobs: " + e.message);
    return;
  }

  appendLog(`Found ${jobUrls.length} jobs`);

  for (const url of jobUrls) {
    if (runAborted || stats.submitted >= config.max_applications) break;
    await processJob(url, config, stats);
  }
}

async function processJob(jobUrl, config, stats) {
  if (runAborted) return;
  stats.scanned++;

  try {
    await chrome.tabs.update(activeTabId, { url: jobUrl });
    await sleep(2500);

    const result = await chrome.scripting.executeScript({
      target: { tabId: activeTabId },
      func: checkAndApplyJob,
      args: [config]
    });

    const outcome = result[0]?.result;
    if (!outcome) { stats.failures++; return; }

    if (outcome.status === "submitted") {
      stats.submitted++;
      appendLog(`✓ Applied: ${outcome.title} @ ${outcome.company}`);
      // Report to server
      const { token, server } = await getStorage(["token", "server"]);
      fetch(`${(server || DEFAULT_SERVER)}/api/ext/report_job`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ url: jobUrl, title: outcome.title, company: outcome.company, status: "submitted" })
      }).catch(() => {});
    } else if (outcome.status === "skipped") {
      stats.skipped++;
    } else if (outcome.status === "no_easy_apply") {
      stats.skipped++;
    } else {
      stats.failures++;
      appendLog(`✗ Failed: ${outcome.reason || "unknown"}`);
    }
  } catch (e) {
    stats.failures++;
    appendLog(`✗ Error on job: ${e.message}`);
  }

  await sleep(1500 + Math.random() * 1000);
}

async function finishRun(stats) {
  await setStorage({ running: false });

  // Close the LinkedIn tab
  if (activeTabId) {
    try { await chrome.tabs.remove(activeTabId); } catch {}
    activeTabId = null;
  }

  // Report run to server
  try {
    const { token, server } = await getStorage(["token", "server"]);
    await fetch(`${(server || DEFAULT_SERVER)}/api/ext/report_run`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
      body: JSON.stringify(stats)
    });
  } catch {}

  // Show notification
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon48.png",
    title: "LinkedIn AutoApply",
    message: stats.error
      ? `Run failed: ${stats.error}`
      : `Done! Applied to ${stats.submitted} jobs today.`
  });
}

// ── Tab helpers ───────────────────────────────────────────────────────────

function openTab(url) {
  return new Promise(resolve => {
    if (activeTabId) {
      chrome.tabs.update(activeTabId, { url }, tab => {
        if (chrome.runtime.lastError) {
          // Tab was closed, create new one
          chrome.tabs.create({ url, active: false }, resolve);
        } else {
          resolve(tab || { id: activeTabId });
        }
      });
    } else {
      chrome.tabs.create({ url, active: false }, resolve);
    }
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── Log helper ────────────────────────────────────────────────────────────

async function appendLog(msg) {
  const { run_log } = await getStorage(["run_log"]);
  const current = run_log || "";
  const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
  console.log("[AutoApply]", msg);
  await setStorage({ run_log: current + line + "\n" });
}

// ── Message handling (from popup) ─────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "RUN_NOW") {
    startRun();
  } else if (msg.type === "STOP_RUN") {
    runAborted = true;
    setStorage({ running: false });
  } else if (msg.type === "SET_AUTO") {
    if (msg.enabled) scheduleDaily();
    else cancelDaily();
  }
  sendResponse({ ok: true });
  return true;
});

// ── On install / startup ──────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async () => {
  const { auto_apply_enabled } = await getStorage(["auto_apply_enabled"]);
  if (auto_apply_enabled) scheduleDaily();
});

chrome.runtime.onStartup.addListener(async () => {
  const { auto_apply_enabled } = await getStorage(["auto_apply_enabled"]);
  if (auto_apply_enabled) scheduleDaily();
});

// ══════════════════════════════════════════════════════════════════════════
// Functions injected into LinkedIn page via chrome.scripting.executeScript
// ══════════════════════════════════════════════════════════════════════════

function extractJobUrls() {
  const anchors = document.querySelectorAll("a");
  const urls = [];
  anchors.forEach(a => {
    const href = a.href || "";
    if (href.includes("/jobs/view/")) {
      const clean = href.split("?")[0];
      if (!urls.includes(clean)) urls.push(clean);
    }
  });
  return urls;
}

async function checkAndApplyJob(config) {
  // Helper: sleep inside injected function
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const title = document.querySelector("h1")?.innerText?.trim() || "";
  const company = (
    document.querySelector(".jobs-unified-top-card__company-name")
    || document.querySelector(".job-details-jobs-unified-top-card__company-name")
    || document.querySelector("a[data-tracking-control-name*='company']")
  )?.innerText?.trim() || "";

  // Find Easy Apply button
  let applyBtn = null;
  const selectors = [
    "button.jobs-apply-button",
    "button[aria-label*='Easy Apply']",
    "button:contains('Easy Apply')"
  ];

  for (const sel of selectors) {
    try {
      const el = document.querySelector(sel);
      if (el) { applyBtn = el; break; }
    } catch {}
  }

  // Fallback: scan all buttons
  if (!applyBtn) {
    for (const btn of document.querySelectorAll("button")) {
      const txt = (btn.innerText || "").toLowerCase();
      const aria = (btn.getAttribute("aria-label") || "").toLowerCase();
      if ((txt.includes("easy apply") || aria.includes("easy apply")) && !txt.includes("continue")) {
        applyBtn = btn;
        break;
      }
    }
  }

  if (!applyBtn) return { status: "no_easy_apply", title, company };

  // Check it's not an external apply button
  const btnText = (applyBtn.innerText || "").toLowerCase();
  if (!btnText.includes("easy apply") && !(applyBtn.getAttribute("aria-label") || "").toLowerCase().includes("easy apply")) {
    return { status: "no_easy_apply", title, company };
  }

  // Click Easy Apply
  applyBtn.click();
  await sleep(2000);

  // Fill the modal form
  let pageNum = 0;
  const maxPages = 8;

  while (pageNum < maxPages) {
    pageNum++;

    // Fill text inputs
    const inputs = document.querySelectorAll(".jobs-easy-apply-content input, .jobs-easy-apply-content textarea, .artdeco-modal input, .artdeco-modal textarea");
    for (const input of inputs) {
      const type = (input.getAttribute("type") || "text").toLowerCase();
      if (["hidden", "submit", "button", "file"].includes(type)) continue;
      if (input.value && input.value.trim()) continue;

      const meta = [
        input.getAttribute("name"),
        input.getAttribute("id"),
        input.getAttribute("placeholder"),
        input.getAttribute("aria-label"),
        input.closest("div")?.querySelector("label")?.innerText
      ].filter(Boolean).join(" ").toLowerCase();

      let val = null;
      if (meta.includes("phone") || meta.includes("mobile")) val = config.phone;
      else if (meta.includes("name") && !meta.includes("company")) val = config.full_name;
      else if (meta.includes("city") || meta.includes("location")) val = config.location;
      else if (meta.includes("salary")) val = config.salary_answer;
      else if (meta.includes("year") || meta.includes("graduation")) val = config.graduation_year;
      else if (meta.includes("experience")) val = String(config.experience_years);

      if (val) {
        input.focus();
        input.value = val;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        await sleep(200);
      }
    }

    // Handle radio / select for work authorization
    const radios = document.querySelectorAll(".artdeco-modal input[type='radio'], .jobs-easy-apply-content input[type='radio']");
    for (const radio of radios) {
      const label = radio.closest("label") || document.querySelector(`label[for="${radio.id}"]`);
      const labelText = (label?.innerText || "").toLowerCase();
      if (labelText.includes("yes") && (
        (radio.closest("fieldset")?.innerText || "").toLowerCase().includes("authorized") ||
        (radio.closest("fieldset")?.innerText || "").toLowerCase().includes("work")
      )) {
        radio.click();
        await sleep(200);
      }
    }

    // Look for Next / Submit button
    const modal = document.querySelector(".artdeco-modal, .jobs-easy-apply-modal");
    if (!modal) break;

    const buttons = modal.querySelectorAll("button");
    let nextBtn = null;
    let submitBtn = null;

    for (const btn of buttons) {
      const txt = (btn.innerText || "").trim().toLowerCase();
      if (txt === "submit application" || txt === "submit") submitBtn = btn;
      else if (txt === "next" || txt === "review" || txt === "continue") nextBtn = btn;
    }

    if (submitBtn) {
      submitBtn.click();
      await sleep(2000);

      // Dismiss confirmation
      const dismiss = document.querySelector("button[aria-label='Dismiss']") ||
                      document.querySelector("button.artdeco-modal__dismiss");
      if (dismiss) dismiss.click();

      return { status: "submitted", title, company };
    }

    if (nextBtn) {
      nextBtn.click();
      await sleep(1500);
    } else {
      // Stuck — no recognized button
      const closeBtn = modal.querySelector("button[aria-label='Dismiss']") ||
                       modal.querySelector("button.artdeco-modal__dismiss");
      if (closeBtn) closeBtn.click();
      return { status: "failed", reason: "No next/submit button found", title, company };
    }
  }

  return { status: "failed", reason: "Exceeded max pages in apply flow", title, company };
}
