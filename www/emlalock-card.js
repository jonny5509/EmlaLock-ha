/* EmlaLock Lovelace card
 * Automatically loaded and registered by the EmlaLock integration.
 * No manual Lovelace resource is required.
 */

class EmlaLockCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._root = document.createElement("div");
    this.shadowRoot.appendChild(this._root);
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _findEntity(...suffixes) {
    if (!this._hass?.states) return null;
    const states = Object.values(this._hass.states);
    const wanted = suffixes.map((value) => value.toLowerCase());
    return states.find((item) => {
      const id = item.entity_id.toLowerCase();
      const name = String(item.attributes?.friendly_name || "").toLowerCase();
      if (!id.includes("emlalock") && !name.includes("emlalock")) return false;
      return wanted.some((suffix) =>
        id.endsWith(`_${suffix}`) || name === `emlalock ${suffix.replaceAll("_", " ")}`
      );
    }) || null;
  }

  _value(entity, fallback = "—") {
    if (!entity || entity.state === "unknown" || entity.state === "unavailable") return fallback;
    return entity.state;
  }

  _findButton(...suffixes) {
    if (!this._hass?.states) return null;
    const wanted = suffixes.map((value) => value.toLowerCase());
    return Object.values(this._hass.states).find((item) => {
      if (!item.entity_id.toLowerCase().startsWith("button.")) return false;
      const id = item.entity_id.toLowerCase();
      const name = String(item.attributes?.friendly_name || "").toLowerCase();
      if (!id.includes("emlalock") && !name.includes("emlalock")) return false;
      return wanted.some((suffix) =>
        id.endsWith(`_${suffix}`) || name === `emlalock ${suffix.replaceAll("_", " ")}`
      );
    }) || null;
  }

  async _press(entityId) {
    if (!this._hass || !entityId) return;
    await this._hass.callService("button", "press", { entity_id: entityId });
  }

  _render() {
    if (!this._hass) return;

    const passed = this._findEntity("time_in_lock", "time_passed", "passed");
    const remaining = this._findEntity("time_remaining", "remaining");
    const maximum = this._findEntity("maximum", "maximum_duration");
    const minimum = this._findEntity("minimum", "minimum_duration");

    const buttons = [
      ["−1 hour", "subtract_1_hour", "subtract 1 hour"],
      ["+1 hour", "add_1_hour", "add 1 hour"],
      ["−1 day", "subtract_1_day", "subtract 1 day"],
      ["+1 day", "add_1_day", "add 1 day"],
    ].map(([label, ...suffixes]) => ({
      label,
      entity: this._findButton(...suffixes),
    }));

    this._root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          overflow: hidden;
          border-radius: 24px;
          background: #1b1d1e;
          color: #f4f5f7;
          border: 1px solid #34383b;
          box-shadow: none;
        }
        .card {
          padding: 16px;
          font-family: var(--paper-font-body1_-_font-family, Arial, sans-serif);
        }
        .sensors {
          display: flex;
          flex-direction: column;
          gap: 9px;
        }
        .row {
          display: flex;
          align-items: center;
          min-height: 65px;
          border-radius: 17px;
          background: #242729;
          padding: 10px 14px;
          box-sizing: border-box;
        }
        .row-icon {
          width: 40px;
          flex: 0 0 40px;
          color: #d8dde5;
          font-size: 24px;
          text-align: center;
        }
        .row-content {
          min-width: 0;
          flex: 1;
          padding-left: 8px;
        }
        .label {
          color: #aeb7c5;
          font-size: 13px;
          font-weight: 700;
          letter-spacing: .6px;
          text-transform: uppercase;
        }
        .value {
          color: #f4f5f7;
          font-size: 18px;
          font-weight: 600;
          margin-top: 4px;
          overflow-wrap: anywhere;
        }
        .actions {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 9px;
          margin-top: 12px;
        }
        .action {
          min-height: 48px;
          border: 0;
          border-radius: 15px;
          background: #242729;
          color: #f4f5f7;
          font: inherit;
          font-weight: 700;
          cursor: pointer;
        }
        .action:hover:not(:disabled) { background: #303437; }
        .action:disabled { opacity: .42; cursor: default; }
        @media (max-width: 430px) {
          .row { min-height: 61px; }
          .value { font-size: 16px; }
        }
      </style>
      <ha-card>
        <div class="card">
          <div class="sensors">
            ${this._row("⏱", "Time elapsed", this._value(passed))}
            ${this._row("⌛", "Time remaining", this._value(remaining))}
            ${this._row("⏱", "Minimum", this._value(minimum))}
            ${this._row("⏱", "Maximum", this._value(maximum))}
          </div>
          <div class="actions">
            ${buttons.map((button, index) => `
              <button class="action" data-action="${index}" ${!button.entity || button.entity.state === "unavailable" ? "disabled" : ""}>
                ${button.label}
              </button>
            `).join("")}
          </div>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll(".action").forEach((element) => {
      element.addEventListener("click", () => {
        const button = buttons[Number(element.dataset.action)];
        if (button?.entity) this._press(button.entity.entity_id);
      });
    });
  }

  _row(icon, label, value) {
    return `<div class="row"><div class="row-icon">${icon}</div><div class="row-content"><div class="label">${label}</div><div class="value">${this._escape(value)}</div></div></div>`;
  }

  _escape(value) {
    return String(value ?? "—")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

customElements.define("emlalock-card", EmlaLockCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "emlalock-card",
  name: "EmlaLock Card",
  description: "A minimal EmlaLock card showing elapsed, remaining, minimum, and maximum time with four duration controls.",
  preview: true,
});
