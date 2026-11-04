/**
 * Lovelace card for WABot Studio: connection status + a quick form to send a WhatsApp message.
 * Registered automatically by the integration (frontend.add_extra_js_url) — no manual resource
 * setup needed. Config:
 *   type: custom:wabot-studio-card
 *   entity: sensor.wabot_studio_<account>_status
 *   notify_service: notify.wabot_studio_<account>
 *   title: WABot Studio (optional)
 */
class WabotStudioCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("wabot-studio-card: 'entity' (the status sensor) is required");
    }
    if (!config.notify_service) {
      throw new Error("wabot-studio-card: 'notify_service' (e.g. notify.wabot_studio_kevin) is required");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._updateStatus();
  }

  getCardSize() {
    return 3;
  }

  _render() {
    this.innerHTML = `
      <ha-card header="${this._config.title || "WABot Studio"}">
        <style>
          .wb-content { display: flex; flex-direction: column; gap: 12px; padding: 0 16px 16px; }
          .wb-status { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--secondary-text-color); }
          .wb-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--disabled-color, #9e9e9e); flex-shrink: 0; }
          .wb-dot.connected { background: var(--state-active-color, #4caf50); }
          .wb-dot.error { background: var(--error-color, #db4437); }
          .wb-dot.pending { background: var(--warning-color, #ff9800); }
          ha-textfield, ha-textarea { width: 100%; }
          .wb-actions { display: flex; justify-content: flex-end; }
          .wb-feedback { font-size: 13px; min-height: 18px; }
          .wb-feedback.ok { color: var(--state-active-color, #4caf50); }
          .wb-feedback.error { color: var(--error-color, #db4437); }
        </style>
        <div class="wb-content">
          <div class="wb-status">
            <span class="wb-dot"></span>
            <span class="wb-status-text">—</span>
          </div>
          <ha-textfield class="wb-target" label="Contatto o gruppo (numero/JID)"></ha-textfield>
          <ha-textarea class="wb-message" label="Messaggio" rows="3"></ha-textarea>
          <div class="wb-actions">
            <mwc-button class="wb-send" raised>Invia</mwc-button>
          </div>
          <div class="wb-feedback"></div>
        </div>
      </ha-card>
    `;
    this.querySelector(".wb-send").addEventListener("click", () => this._send());
  }

  _updateStatus() {
    if (!this._config || !this._hass) return;
    const stateObj = this._hass.states[this._config.entity];
    const dot = this.querySelector(".wb-dot");
    const text = this.querySelector(".wb-status-text");
    if (!stateObj) {
      if (text) text.textContent = `Entità ${this._config.entity} non trovata`;
      return;
    }
    const state = stateObj.state;
    if (dot) {
      dot.classList.remove("connected", "error", "pending");
      if (state === "CONNECTED") dot.classList.add("connected");
      else if (state === "ERROR") dot.classList.add("error");
      else if (state === "CONNECTING" || state === "QR_REQUIRED") dot.classList.add("pending");
    }
    if (text) text.textContent = state;
  }

  async _send() {
    const targetField = this.querySelector(".wb-target");
    const messageField = this.querySelector(".wb-message");
    const feedback = this.querySelector(".wb-feedback");
    const target = (targetField.value || "").trim();
    const message = (messageField.value || "").trim();

    if (!target || !message) {
      feedback.textContent = "Inserisci destinatario e messaggio.";
      feedback.className = "wb-feedback error";
      return;
    }

    const [domain, service] = this._config.notify_service.split(".");
    try {
      await this._hass.callService(domain, service, { message, target });
      feedback.textContent = "Inviato!";
      feedback.className = "wb-feedback ok";
      messageField.value = "";
    } catch (err) {
      feedback.textContent = `Errore: ${err.message || err}`;
      feedback.className = "wb-feedback error";
    }
  }
}

customElements.define("wabot-studio-card", WabotStudioCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "wabot-studio-card",
  name: "WABot Studio",
  description: "Stato connessione e invio rapido di messaggi WhatsApp tramite WABot Studio.",
});
