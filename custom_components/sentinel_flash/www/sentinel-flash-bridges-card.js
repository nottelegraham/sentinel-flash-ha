/* Sentinel Flash - bridges card
 *
 *   type: custom:sentinel-flash-bridges-card
 *   title: Sentinel Flash        (optional)
 *   show_offline: true           (optional; false hides bridges that aren't answering)
 *
 * One tile per Sentinel Flash bridge the integration knows about. It reads the
 * integration's devices and entities directly, so a bridge found on the network
 * appears here without editing the dashboard. Online bridges first, then offline
 * ones (dimmed). "Open" opens the bridge's own page in a new tab or, in the phone
 * app, the browser; that needs your phone or computer on the home network.
 * Light theme, one column on a phone, more on wider screens. Ships with the
 * integration; no other cards needed.
 */
const VERSION = "0.1.0";
const PLATFORM = "sentinel_flash";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ago = (iso) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (!isFinite(s)) return "";
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 129600) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
};

const STYLE = `
  :host { display: block; }
  ha-card { background: #ffffff; color: #1c2430; border-radius: 12px; padding: 14px; }
  .head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin: 0 2px 12px; }
  .title { font-size: 18px; font-weight: 600; color: #0b3d6e; }
  .count { font-size: 13px; color: #5b6676; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
  .tile { border: 1px solid #dbe3ec; border-radius: 10px; padding: 12px; background: #f7fafd; display: flex; flex-direction: column; gap: 6px; }
  .tile.off { background: #f4f5f7; opacity: .72; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .name { font-weight: 600; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pill { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
  .pill.on { background: #e3f4e8; color: #1b7a3a; }
  .pill.off { background: #eceff3; color: #6b7480; }
  .meta { font-size: 13px; color: #4a5565; line-height: 1.45; }
  .meta b { color: #1c2430; font-weight: 600; }
  .actions { display: flex; gap: 8px; margin-top: 4px; }
  a.btn, button.btn { font: inherit; font-size: 13px; font-weight: 600; text-decoration: none; cursor: pointer;
    border-radius: 8px; padding: 7px 12px; border: 1px solid #0a5fa8; }
  a.btn { background: #0a5fa8; color: #fff; }
  button.btn { background: #fff; color: #0a5fa8; }
  .empty { font-size: 14px; color: #5b6676; padding: 6px 2px; }
`;

class SentinelFlashBridgesCard extends HTMLElement {
  static getStubConfig() { return {}; }

  setConfig(config) {
    this._config = { title: "Sentinel Flash", show_offline: true, ...(config || {}) };
    this._key = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 2 + Math.ceil(this._bridges().length / 2) * 3; }
  getGridOptions() { return { columns: 12, min_columns: 6 }; }

  _bridges() {
    const h = this._hass;
    if (!h || !h.entities || !h.devices) return [];
    const byDev = {};
    for (const ent of Object.values(h.entities)) {
      if (ent.platform !== PLATFORM || !ent.device_id) continue;
      const key = ent.translation_key || "";
      (byDev[ent.device_id] ||= {})[key] = h.states[ent.entity_id];
    }
    const out = [];
    for (const [id, e] of Object.entries(byDev)) {
      const dev = h.devices[id];
      if (!dev || dev.disabled_by) continue;
      const online = e.online ? e.online.state === "on" : false;
      const conn = e.connected_device;
      out.push({
        id, online,
        name: dev.name_by_user || dev.name || "Sentinel Flash",
        model: (dev.model || "").replace(/^Sentinel Flash /, ""),
        fw: e.firmware && !["unavailable", "unknown"].includes(e.firmware.state) ? e.firmware.state : dev.sw_version,
        device: conn && !["unavailable", "unknown"].includes(conn.state) ? conn.state : null,
        devFw: conn && conn.attributes ? conn.attributes.device_firmware : null,
        busy: !!(conn && conn.attributes && conn.attributes.job_running),
        port: e.active_port && !["unavailable", "unknown"].includes(e.active_port.state) ? e.active_port.state : null,
        since: e.online ? e.online.last_changed : null,
        url: dev.configuration_url || (e.online && e.online.attributes.url) || null,
      });
    }
    out.sort((a, b) => (b.online - a.online) || a.name.localeCompare(b.name));
    return this._config.show_offline ? out : out.filter((b) => b.online);
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const list = this._bridges();
    const key = JSON.stringify([this._config, list]);
    if (key === this._key) return;  // nothing visible changed
    this._key = key;
    const online = list.filter((b) => b.online).length;
    const tiles = list.map((b) => {
      const lines = [];
      if (b.model || b.fw) lines.push(`${esc(b.model || "Bridge")}${b.fw ? ` · firmware <b>${esc(b.fw)}</b>` : ""}`);
      if (b.online) {
        lines.push(`USB: <b>${esc(b.device || "—")}</b>${b.devFw ? ` · v${esc(b.devFw)}` : ""}`);
        if (b.port) lines.push(`Active port: <b>${esc(b.port)}</b>`);
        if (b.busy) lines.push(`<b>Job running</b>`);
      } else if (b.since) {
        lines.push(`Not answering since ${esc(ago(b.since))}`);
      }
      const open = b.url
        ? `<a class="btn" href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">Open</a>` : "";
      return `<div class="tile ${b.online ? "" : "off"}">
        <div class="row"><span class="name" title="${esc(b.name)}">${esc(b.name)}</span>
          <span class="pill ${b.online ? "on" : "off"}">${b.online ? "Online" : "Offline"}</span></div>
        <div class="meta">${lines.join("<br>")}</div>
        <div class="actions">${open}<button class="btn" data-dev="${esc(b.id)}">Details</button></div>
      </div>`;
    }).join("");
    const empty = this._hass && !list.length
      ? `<div class="empty">No Sentinel Flash bridges yet. Bridges on firmware 0.13.5 or later are added automatically when they're on your network.</div>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>
      <div class="head"><span class="title">${esc(this._config.title)}</span>
        <span class="count">${list.length ? `${online} of ${list.length} online` : ""}</span></div>
      <div class="grid">${tiles}</div>${empty}</ha-card>`;
    this.shadowRoot.querySelectorAll("button[data-dev]").forEach((btn) =>
      btn.addEventListener("click", () => {
        history.pushState(null, "", `/config/devices/device/${btn.dataset.dev}`);
        window.dispatchEvent(new CustomEvent("location-changed"));
      }));
  }
}

if (!customElements.get("sentinel-flash-bridges-card")) {
  customElements.define("sentinel-flash-bridges-card", SentinelFlashBridgesCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "sentinel-flash-bridges-card",
    name: "Sentinel Flash bridges",
    description: "Every Sentinel Flash on your network, added automatically.",
  });
  console.info(`%c SENTINEL-FLASH-BRIDGES-CARD %c ${VERSION} `, "background:#0a5fa8;color:#fff", "");
}
