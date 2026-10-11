// options.js — minimal settings page.
//
// Design source: SPEC-preflight-checker_design.md
//   - "非機能": "トークンはserver起動時に生成して~/.config/studio/preflight-token
//     に書き、拡張のoptionsページに人間が1回貼る"

const tokenInput = document.getElementById("token");
const saveButton = document.getElementById("save");
const saveStatus = document.getElementById("saveStatus");
const testButton = document.getElementById("testConnection");
const healthStatus = document.getElementById("healthStatus");

async function loadToken() {
  const { preflightToken } = await chrome.storage.local.get("preflightToken");
  if (preflightToken) {
    tokenInput.value = preflightToken;
  }
}

saveButton.addEventListener("click", async () => {
  const value = tokenInput.value.trim();
  await chrome.storage.local.set({ preflightToken: value });
  saveStatus.textContent = "Saved.";
  saveStatus.style.color = "green";
  setTimeout(() => {
    saveStatus.textContent = "";
  }, 2000);
});

testButton.addEventListener("click", () => {
  healthStatus.textContent = "Checking...";
  healthStatus.style.color = "inherit";
  chrome.runtime.sendMessage({ type: "health" }, (response) => {
    if (chrome.runtime.lastError) {
      healthStatus.textContent = `Error: ${chrome.runtime.lastError.message}`;
      healthStatus.style.color = "red";
      return;
    }
    if (response && response.ok) {
      const llm = response.data && response.data.llm ? "available" : "unavailable";
      healthStatus.textContent = `Backend online (LLM: ${llm})`;
      healthStatus.style.color = "green";
    } else {
      healthStatus.textContent = "Backend offline";
      healthStatus.style.color = "red";
    }
  });
});

loadToken();
