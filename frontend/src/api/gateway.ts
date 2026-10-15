export interface GatewayFrame {
  type: 'req' | 'res' | 'event'
  id?: string
  method?: string
  params?: any
  ok?: boolean
  payload?: any
  error?: any
  event?: string
  seq?: number
}

export const ownerMode = new URLSearchParams(location.search).get('owner') === '1'
export const demoMode = Boolean(import.meta.env.VITE_MUXTRAIL_DEMO_WS_URL) && !ownerMode

export function defaultGatewayUrl() {
  if (demoMode) return import.meta.env.VITE_MUXTRAIL_DEMO_WS_URL
  const configured = import.meta.env.VITE_MUXTRAIL_WS_URL
  if (configured) return configured
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/ws`
}

export class GatewayClient {
  private ws: WebSocket | null = null
  private connectPromise: Promise<any> | null = null
  private requestId = 0
  private pending = new Map<string, { resolve: (v: any) => void; reject: (e: any) => void }>()
  private eventHandlers = new Map<string, ((payload: any) => void)[]>()
  private statusHandlers: ((status: string) => void)[] = []
  private url = ''
  private manualClose = false
  private reconnectAttempt = 0
  private reconnectTimer: number | null = null

  connect(url = defaultGatewayUrl()): Promise<any> {
    if (this.ws?.readyState === WebSocket.OPEN) return Promise.resolve(true)
    if (this.connectPromise) return this.connectPromise

    this.url = url
    this.manualClose = false
    this.connectPromise = new Promise((resolve, reject) => {
      this.ws = new WebSocket(url)
      this.ws.onopen = () => {
        this.emitStatus('handshake')
        this.send('connect', {
          minProtocol: 1, maxProtocol: 3,
          client: {
            id: demoMode ? 'public-demo' : 'web-admin',
            version: '0.1.0',
            platform: 'browser',
            mode: demoMode ? 'demo' : 'local',
          }
        }).then((payload) => {
          this.emitStatus('connected')
          this.reconnectAttempt = 0
          resolve(payload)
        }).catch(reject)
      }
      this.ws.onmessage = (ev) => this.handleMessage(JSON.parse(ev.data))
      this.ws.onerror = () => {
        this.emitStatus('error')
        reject(new Error('WebSocket error'))
      }
      this.ws.onclose = () => {
        for (const pending of this.pending.values()) pending.reject(new Error('Connection closed'))
        this.pending.clear()
        this.ws = null
        this.connectPromise = null
        this.emitStatus('disconnected')
        if (!this.manualClose) this.scheduleReconnect()
      }
    })

    return this.connectPromise
  }

  async send(method: string, params: any = {}, timeoutMs = 180000): Promise<any> {
    if (!this.ws) throw new Error('Not connected')
    const id = `req-${++this.requestId}`
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws!.send(JSON.stringify({ type: 'req', id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error('Request timeout'))
        }
      }, timeoutMs)
    })
  }

  on(event: string, handler: (payload: any) => void) {
    if (!this.eventHandlers.has(event)) this.eventHandlers.set(event, [])
    this.eventHandlers.get(event)!.push(handler)
  }

  off(event: string, handler: (payload: any) => void) {
    const handlers = this.eventHandlers.get(event) || []
    this.eventHandlers.set(event, handlers.filter((item) => item !== handler))
  }

  onStatus(handler: (status: string) => void) {
    this.statusHandlers.push(handler)
  }

  private handleMessage(frame: GatewayFrame) {
    if (frame.type === 'res' && frame.id) {
      const p = this.pending.get(frame.id)
      if (p) {
        this.pending.delete(frame.id)
        frame.ok
          ? p.resolve(frame.payload)
          : p.reject(new Error(frame.error?.message || 'Gateway request failed'))
      }
    } else if (frame.type === 'event' && frame.event) {
      const handlers = this.eventHandlers.get(frame.event) || []
      handlers.forEach(h => h(frame.payload))
    }
  }

  private emitStatus(status: string) {
    this.statusHandlers.forEach((handler) => handler(status))
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null) return
    const delay = Math.min(1000 * 2 ** this.reconnectAttempt, 15000)
    this.reconnectAttempt += 1
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      void this.connect(this.url).catch(() => undefined)
    }, delay)
  }

  disconnect() {
    this.manualClose = true
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    this.ws?.close()
    this.ws = null
    this.connectPromise = null
  }
}

export const gateway = new GatewayClient()
