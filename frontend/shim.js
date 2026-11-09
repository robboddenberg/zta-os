// ZTA OS API Bridge & Offline-Safe Helper Shim
window.ZTA_SHIM = {
  version: "1.0.0",
  formatEurFromCents(cents) {
    const val = Number(cents || 0);
    const sign = val < 0 ? "-" : "";
    const abs = Math.abs(Math.round(val));
    const euros = Math.floor(abs / 100);
    const rem = abs % 100;
    const euroStr = euros.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${sign}${euroStr},${rem.toString().padStart(2, "0")} EUR`;
  },
  async apiFetch(url, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    const resp = await fetch(url, Object.assign({}, options, { headers }));
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = data.detail || data.message || `HTTP Fehler ${resp.status}`;
      const err = new Error(msg);
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  }
};
