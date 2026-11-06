import type { EventPacket, RequestType, Results } from './types'

export class ClientError extends Error {
  constructor(public code: string, public network = false) { super(code) }
}

type Pending = { resolve: (value: unknown) => void; reject: (error: ClientError) => void; timer: ReturnType<typeof setTimeout> }
const idKeys = new Set(['id', 'room_id', 'message_id', 'sender_id', 'created_by', 'next_after_id'])
function safeIds(value: unknown, depth = 0): void {
  if (depth > 64) throw new ClientError('PROTOCOL', true)
  if (!value || typeof value !== 'object') return
  for (const [key, item] of Object.entries(value)) {
    if (idKeys.has(key) && typeof item === 'number' && !Number.isSafeInteger(item)) throw new ClientError('PROTOCOL', true)
    safeIds(item, depth + 1)
  }
}

export class Transport {
  private socket: WebSocket | null = null
  private opening: Promise<void> | null = null
  private pending = new Map<string, Pending>()
  private lastError: ClientError | null = null
  private intentional = false
  constructor(private onEvent: (packet: EventPacket) => void, private onClose: (error: ClientError, intentional: boolean) => void) {}

  connect(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN) return Promise.resolve()
    if (this.socket?.readyState === WebSocket.CONNECTING && this.opening) return this.opening
    this.intentional = false
    this.lastError = null
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${scheme}//${window.location.host}/ws`)
    this.socket = socket
    this.opening = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { this.fail(new ClientError('TIMEOUT', true)); reject(new ClientError('TIMEOUT', true)) }, 10000)
      socket.onopen = () => { clearTimeout(timer); resolve() }
      socket.onmessage = event => {
        if (this.socket !== socket || socket.readyState !== WebSocket.OPEN) return
        try {
          if (typeof event.data !== 'string' || new TextEncoder().encode(event.data).length > 1048576) throw new ClientError('PROTOCOL', true)
          const packet = JSON.parse(event.data) as EventPacket
          if (packet.v !== 1 || !packet.data || typeof packet.data !== 'object') throw new ClientError('PROTOCOL', true)
          safeIds(packet.data)
          if (packet.type === 'RESPONSE') {
            const request = packet.id && this.pending.get(packet.id)
            if (!request || typeof packet.data.ok !== 'boolean') throw new ClientError('PROTOCOL', true)
            clearTimeout(request.timer)
            this.pending.delete(packet.id!)
            if (packet.data.ok) request.resolve(packet.data.result)
            else request.reject(new ClientError((packet.data.error as { code: string }).code))
          } else if (['USERS_UPDATED', 'GROUPS_UPDATED', 'MESSAGE_NEW'].includes(packet.type)) this.onEvent(packet)
          else throw new ClientError('PROTOCOL', true)
        } catch { this.fail(new ClientError('PROTOCOL', true)) }
      }
      socket.onerror = () => { if (this.socket === socket) this.lastError ??= new ClientError('CONNECTION', true) }
      socket.onclose = () => {
        clearTimeout(timer)
        const error = this.lastError || new ClientError('CONNECTION', true)
        reject(error)
        if (this.socket !== socket) return
        this.socket = null
        this.opening = null
        this.rejectAll(error)
        this.onClose(error, this.intentional)
      }
    })
    return this.opening
  }

  request<T extends RequestType>(type: T, data: Record<string, unknown> = {}): Promise<Results[T]> {
    if (this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(new ClientError('CONNECTION', true))
    if (this.pending.size >= 128) return Promise.reject(new ClientError('BUSY'))
    const bytes = crypto.getRandomValues(new Uint8Array(16))
    const id = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(new ClientError('TIMEOUT', true)), 15000)
      this.pending.set(id, { resolve: value => resolve(value as Results[T]), reject, timer })
      try { this.socket!.send(JSON.stringify({ v: 1, id, type, data })) }
      catch { this.fail(new ClientError('CONNECTION', true)) }
    })
  }

  private rejectAll(error: ClientError) {
    for (const request of this.pending.values()) { clearTimeout(request.timer); request.reject(error) }
    this.pending.clear()
  }
  private fail(error: ClientError) {
    this.lastError = error
    this.rejectAll(error)
    this.socket?.close()
  }
  close() {
    this.intentional = true
    this.rejectAll(new ClientError('CLOSED', true))
    this.socket?.close(1000)
  }
}
