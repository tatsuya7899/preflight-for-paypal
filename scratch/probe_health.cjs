// Reproduce waitHealth polling against whatever currently serves 127.0.0.1:8000
const BASE = "http://127.0.0.1:8000";
async function isOurs(resp) {
  if (!resp.ok) return false;
  const j = await resp.json().catch(() => null);
  return !!(j && typeof j === "object" && "fixture" in j);
}
(async () => {
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(BASE + "/health");
      const ct = r.headers.get("content-type");
      console.log(i, "status", r.status, "ct", ct, "isOurs", await isOurs(r));
    } catch (e) {
      console.log(i, "ERR", e.message);
    }
    await new Promise((r) => setTimeout(r, 250));
  }
})();
