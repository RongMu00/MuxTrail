/** REST API client */

const BASE = (import.meta.env.VITE_MUXTRAIL_API_BASE || '/api').replace(/\/$/, '')

export async function fetchJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    credentials: 'include',
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return resp.json()
}

export const api = {
  getConfig: () => fetchJson<any>('/config'),
  getSessions: () => fetchJson<any>('/sessions'),
  getModels: () => fetchJson<any>('/models'),
  getChannelStatus: () => fetchJson<any>('/channels/status'),
  getStatus: () => fetchJson<any>('/status'),
  getDiagnostics: () => fetchJson<any>('/diagnostics'),
}
