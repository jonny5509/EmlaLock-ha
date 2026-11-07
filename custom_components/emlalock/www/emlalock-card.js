/* EmlaLock Lovelace card
 * Dashboard-safe custom card. Supports automatic entity discovery and
 * optional explicit entity IDs for installations with renamed entities.
 */
class EmlaLockCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._root = document.createElement("div");
    this.shadowRoot.appendChild(this._root);
    this._config = {};
    this._busy = new Set();
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("EmlaLock Card: configuration must be an object");
    }
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._config?.show_actions === false ? 5 : 7;
  }

  static getStubConfig() {
    return { type: "custom:emlalock-card" };
  }

  _states() {
    return this._hass?.states ? Object.values(this._hass.states) : [];
  }

  _findEntity(key, ...suffixes) {
    const configured = this._config?.entities?.[key];
    if (configured && this._hass?.states?.[configured]) {
      return this._hass.states[configured];
    }
    const wanted = suffixes.map((value) => value.toLowerCase());
    return this._states().find((entity) => {
      const id = String(entity.entity_id || "").toLowerCase();
      const name = String(entity.attributes?.friendly_name || "").toLowerCase();
      if (!id.includes("emlalock") && !name.includes("emlalock")) return false;
      return wanted.some((suffix) =>
        id.endsWith("_" + suffix) ||
        name === "emlalock " + suffix.replaceAll("_", " ") ||
        name.replaceAll(" ", "_").endsWith("_" + suffix)
      );
    }) || null;
  }

  _findButton(key, ...suffixes) {
    const configured = this._config?.entities?.[key];
    if (configured && this._hass?.states?.[configured]) {
      return this._hass.states[configured];
    }
    const wanted = suffixes.map((value) => value.toLowerCase());
    return this._states().find((entity) => {
      const id = String(entity.entity_id || "").toLowerCase();
      if (!id.startsWith("button.")) return false;
      const name = String(entity.attributes?.friendly_name || "").toLowerCase();
      return wanted.some((suffix) =>
        id.endsWith("_" + suffix) ||
        name === "emlalock " + suffix.replaceAll("_", " ") ||
        name.replaceAll(" ", "_").endsWith("_" + suffix)
      );
    }) || null;
  }

  _value(entity) {
    if (!entity || entity.state === "unknown" || entity.state === "unavailable") {
      return "Not available";
    }
    try {
      if (typeof this._hass?.formatEntityState === "function") {
        return this._hass.formatEntityState(entity);
      }
    } catch (_error) {
      // Fall back to the raw state for older Home Assistant versions.
    }
    return entity.state;
  }

  async _press(entityId, index) {
    if (!this._hass || !entityId || this._busy.has(index)) return;
    this._busy.add(index);
    this._render();
    try {
      await this._hass.callService("button", "press", { entity_id: entityId });
    } catch (error) {
      console.error("EmlaLock Card: unable to run button action", error);
    } finally {
      this._busy.delete(index);
      this._render();
    }
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;

    const rows = [
      ["Time locked / elapsed", this._findEntity("time_passed", "time_passed", "time_in_lock", "passed")],
      ["Time remaining", this._findEntity("time_remaining", "time_remaining", "remaining")],
      ["Maximum duration", this._findEntity("maximum", "maximum", "maximum_duration")],
    ];

    const actions = [
      { label: "+1 hour", key: "add_1_hour", suffix: "add_1_hour" },
      { label: "−1 hour", key: "subtract_1_hour", suffix: "subtract_1_hour" },
      { label: "+1 day", key: "add_1_day", suffix: "add_1_day" },
      { label: "−1 day", key: "subtract_1_day", suffix: "subtract_1_day" },
    ].map((action) => ({
      ...action,
      entity: this._findButton(action.key, action.suffix),
    }));

    const visibleRows = rows.filter(([, entity]) => entity);
    const title = this._escape(this._config.title || "EmlaLock");
    const showActions = this._config.show_actions !== false;

    this._root.innerHTML = `
      <style>
        :host { display: block; min-width: 0; }
        ha-card {
          overflow: hidden;
          color: var(--primary-text-color);
          background: var(--ha-card-background, var(--card-background-color, var(--paper-card-background-color)));
          border: 1px solid var(--divider-color);
          border-radius: var(--ha-card-border-radius, 16px);
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .card { padding: 16px; font-family: var(--paper-font-body1_-_font-family, inherit); }
        .heading { margin: 0 0 12px; color: var(--primary-text-color); font-size: 1.15rem; font-weight: 600; }
        .sensors { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr)); gap: 8px; }
        .row {
          display: flex; align-items: center; min-height: 62px; min-width: 0;
          box-sizing: border-box; padding: 10px 12px; border-radius: 12px;
          background: var(--ha-card-background, var(--secondary-background-color));
          border: 1px solid var(--divider-color);
        }
        .row-icon { width: 34px; flex: 0 0 34px; color: var(--secondary-text-color); font-size: 20px; text-align: center; }
        .row-content { min-width: 0; flex: 1; padding-left: 8px; }
        .label { color: var(--secondary-text-color); font-size: 11px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase; }
        .value { margin-top: 4px; color: var(--primary-text-color); font-size: 16px; font-weight: 600; overflow-wrap: anywhere; }
        .actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
        .action {
          min-width: 0; min-height: 44px; padding: 8px 12px; border: 0; border-radius: 12px;
          background: var(--primary-color); color: var(--text-primary-color, white);
          font: inherit; font-weight: 600; cursor: pointer;
        }
        .action:hover:not(:disabled) { filter: brightness(1.08); }
        .action:focus-visible { outline: 2px solid var(--primary-text-color); outline-offset: 2px; }
        .action:disabled { opacity: .45; cursor: not-allowed; }
        .empty { color: var(--secondary-text-color); padding: 8px 0; }
        @media (max-width: 360px) { .card { padding: 12px; } .value { font-size: 14px; } }
      </style>
      <ha-card>
        <div class="card">
          <h2 class="heading">${title}</h2>
          <div class="sensors">
            ${visibleRows.length ? visibleRows.map(([label, entity], index) =>
              this._row(["◉", "⏱", "⌛", "▶", "■", "↓", "↑", "🔗"][rows.indexOf(rows.find((row) => row[0] === label))] || "•", label, this._value(entity))
            ).join("") : '<div class="empty">No EmlaLock entities found. Check that the integration is loaded, or set entity IDs in the card configuration.</div>'}
          </div>
          ${showActions ? `
            <div class="actions">
              ${actions.map((action, index) => `
                <button class="action" data-action="${index}" ${!action.entity || ["unavailable", "unknown"].includes(action.entity.state) || this._busy.has(index) ? "disabled" : ""}>
                  ${this._busy.has(index) ? "Working…" : action.label}
                </button>
              `).join("")}
            </div>
          ` : ""}
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll(".action").forEach((element) => {
      element.addEventListener("click", () => {
        const index = Number(element.dataset.action);
        const action = actions[index];
        if (action?.entity) this._press(action.entity.entity_id, index);
      });
    });
  }

  _row(icon, label, value) {
    return `<div class="row"><div class="row-icon" aria-hidden="true">${icon}</div><div class="row-content"><div class="label">${this._escape(label)}</div><div class="value">${this._escape(value)}</div></div></div>`;
  }

  _escape(value) {
    return String(value ?? "—")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
}

if (!customElements.get("emlalock-card")) {
  customElements.define("emlalock-card", EmlaLockCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "emlalock-card")) {
  window.customCards.push({
    type: "emlalock-card",
    name: "EmlaLock Card",
    description: "Session information and duration controls for EmlaLock.",
    preview: true,
    documentationURL: "https://github.com/jonny5509/EmlaLock-ha",
  });
}
