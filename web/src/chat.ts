import { ClientError, Transport } from './transport'
import { MAX_FILE_BYTES, fromBase64, sha256Hex, toBase64 } from './files'
import type { Attachment, EventPacket, Message, Page, Room, State, Transfer, User } from './types'

const empty = (): State => ({ phase: 'disconnected', authBusy: false, user: null, users: [], rooms: {}, messages: {}, history: {}, ai: {}, uploads: {}, downloads: {}, drafts: {}, unread: {}, notices: {}, sending: {}, activeRoom: null, groupsLoading: false, highlight: null, error: '', info: '' })
const errors: Record<string, string> = {
  AUTH_FAILED: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', USERNAME_TAKEN: 'ชื่อผู้ใช้นี้ถูกใช้แล้ว กรุณาเลือกชื่อใหม่',
  ALREADY_LOGGED_IN: 'บัญชีนี้เข้าสู่ระบบอยู่แล้ว กรุณาออกจากระบบที่เครื่องเดิมก่อน',
  RATE_LIMITED: 'ลองบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่', AUTH_REQUIRED: 'กรุณาเข้าสู่ระบบใหม่',
  FORBIDDEN: 'คุณยังไม่มีสิทธิ์ใช้งานห้องนี้', INVALID_INPUT: 'ข้อมูลไม่ถูกต้อง กรุณาตรวจชื่อ รหัสผ่าน หรือความยาวข้อความ',
  FRAME_TOO_LARGE: 'ข้อมูลมีขนาดใหญ่เกินไป กรุณาลองโหลดใหม่',
  CONNECTION: 'การเชื่อมต่อขาดหาย หรือเชื่อมต่อ Server ไม่ได้', TIMEOUT: 'Server ไม่ตอบกลับภายในเวลาที่กำหนด',
  PROTOCOL: 'ข้อมูลการเชื่อมต่อไม่สมบูรณ์ กรุณาเข้าสู่ระบบใหม่', BUSY: 'กำลังทำหลายรายการ กรุณารอสักครู่',
  AI_UNAVAILABLE: 'AI สรุปไม่สำเร็จหรือยังไม่พร้อมใช้งาน แชตยังใช้ได้ตามปกติ ลองใหม่ภายหลัง',
  NOT_FOUND: 'ไม่พบไฟล์นี้บน Server', FILE_TOO_LARGE: 'ไฟล์ต้องมีขนาดไม่เกิน 5 MB',
  FILE_CORRUPT: 'ไฟล์ที่ได้รับไม่ตรงกับ SHA-256 จึงไม่บันทึกไฟล์นี้', FILE_REJECTED: 'Server ไม่รับไฟล์นี้ กรุณาตรวจชื่อไฟล์หรือลองส่งใหม่',
}
export function errorText(error: unknown) { return error instanceof ClientError ? errors[error.code] || 'ทำรายการไม่สำเร็จ กรุณาลองใหม่' : 'ทำรายการไม่สำเร็จ กรุณาลองใหม่' }
export function isMember(state: State, room: Room) { return room.members.some(member => member.id === state.user?.id) }
export function roomTitle(state: State, room: Room) { return room.kind === 'group' ? room.name! : room.members.find(member => member.id !== state.user?.id)?.username || 'แชตส่วนตัว' }
const uncertain = 'ยังยืนยันการส่งไม่ได้ ข้อความอาจถูกบันทึกแล้ว เก็บร่างไว้ให้ตรวจสอบก่อนส่งใหม่'
// File requests get a longer timeout and a small window, so a slow link (~3 KB/s)
// does not hit the transport timeout that ends the whole session.
const AI_TIMEOUT = 75000
const PAGE = 50, UPLOAD_WINDOW = 4, DOWNLOAD_WINDOW = 2, DOWNLOAD_CHUNK = 128 * 1024, JUMP_PAGES = 40, FILE_TIMEOUT = 60000
export type SearchFilters = { query?: string; from?: string; to?: string; kind?: 'file' }
// Mark a pipelined request as handled now; awaiting it later still throws.
function handled<T>(promise: Promise<T>) { promise.catch(() => {}); return promise }
function without<T>(record: Record<number, T>, key: number) { const copy = { ...record }; delete copy[key]; return copy }

export class ChatController {
  private state = empty()
  private listeners = new Set<() => void>()
  private transport = new Transport(packet => this.event(packet), (error, intentional) => this.disconnected(error, intentional))
  private epoch = 0
  private revision = -1
  private groupFlight: Promise<void> | null = null
  private groupsDirty = false
  private selection = 0
  private opening = new Map<number, { intent: number | null }>()
  private attempts = 0
  private downloadAttempt = new Map<number, number>()
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  snapshot = () => this.state
  private patch(value: Partial<State>) { this.state = { ...this.state, ...value }; for (const listener of this.listeners) listener() }
  private report(error: unknown) { this.patch({ error: errorText(error) }) }
  clearError() { this.patch({ error: '' }) }
  setDraft(room: number, text: string) { this.patch({ drafts: { ...this.state.drafts, [room]: text } }) }

  async authenticate(register: boolean, username: string, password: string, confirm: string) {
    if (this.state.authBusy || this.state.phase === 'authenticated') return
    const epoch = ++this.epoch
    this.revision = -1
    this.groupFlight = null
    this.opening.clear()
    this.patch({ authBusy: true, phase: 'connecting', error: '', info: '' })
    try {
      await this.transport.connect()
      if (epoch !== this.epoch) return
      this.patch({ phase: 'connected' })
      if (register) {
        await this.transport.request('REGISTER', { username, password, confirm_password: confirm })
        if (epoch === this.epoch) this.patch({ authBusy: false, info: 'สมัครสมาชิกแล้ว กรุณาเข้าสู่ระบบด้วยบัญชีที่สร้าง' })
        return
      }
      const result = await this.transport.request('LOGIN', { username, password })
      if (epoch !== this.epoch) return
      const retained = this.state.user?.id === result.user.id ? this.state : empty()
      // Drafts survive a re-login; messages are reloaded from Server history so
      // nothing missed while disconnected leaves a gap in the transcript.
      this.state = { ...retained, messages: {}, history: {}, ai: {}, unread: {}, uploads: {}, downloads: {}, highlight: null }
      this.patch({ user: result.user, authBusy: false, phase: 'authenticated', users: [], error: '', info: '' })
      void this.loadUsers(epoch)
      void this.refreshGroups()
      void this.loadPrivateRooms(epoch)
      const active = this.state.activeRoom === null ? undefined : this.state.rooms[this.state.activeRoom]
      if (active && isMember(this.state, active)) void this.loadHistory(active.id)
    } catch (error) {
      if (epoch === this.epoch) this.patch({ authBusy: false, error: errorText(error) })
    }
  }

  private async loadUsers(epoch: number) {
    try {
      const result = await this.transport.request('USERS_LIST')
      if (epoch === this.epoch && this.revision < 0) this.patch({ users: result.users })
    } catch (error) { if (epoch === this.epoch) this.report(error) }
  }

  private async loadPrivateRooms(epoch: number) {
    try {
      let after = 0
      while (true) {
        const result = await this.pageRequest(limit => this.transport.request('PRIVATE_ROOM_LIST', { after_id: after, limit }))
        if (epoch !== this.epoch) return
        this.patch({ rooms: { ...this.state.rooms, ...Object.fromEntries(result.rooms.map(room => [room.id, room])) } })
        if (result.next_after_id === null) return
        after = result.next_after_id
      }
    } catch (error) { if (epoch === this.epoch) this.report(error) }
  }

  /** Halve the page size when a page would not fit one 1 MiB frame. */
  private async pageRequest<T>(run: (limit: number) => Promise<T>, limit = PAGE): Promise<T> {
    while (true) {
      try { return await run(limit) }
      catch (error) {
        if (error instanceof ClientError && error.code === 'FRAME_TOO_LARGE' && limit > 1) limit = Math.max(1, Math.floor(limit / 2))
        else throw error
      }
    }
  }

  refreshGroups(): Promise<void> {
    if (this.state.phase !== 'authenticated') return Promise.resolve()
    if (this.groupFlight) { this.groupsDirty = true; return this.groupFlight }
    const epoch = this.epoch
    this.patch({ groupsLoading: true })
    this.groupFlight = (async () => {
      try {
        do {
          this.groupsDirty = false
          const groups: Record<number, Room> = {}
          let after = 0, limit = 50
          while (true) {
            try {
              const result = await this.transport.request('GROUP_LIST', { after_id: after, limit })
              if (epoch !== this.epoch) return
              for (const room of result.groups) groups[room.id] = room
              if (result.next_after_id === null) break
              after = result.next_after_id
            } catch (error) {
              if (error instanceof ClientError && error.code === 'FRAME_TOO_LARGE' && limit > 1) limit = Math.max(1, Math.floor(limit / 2))
              else throw error
            }
          }
          const rooms = Object.fromEntries(Object.entries(this.state.rooms).filter(([, room]) => room.kind === 'private'))
          this.patch({ rooms: { ...rooms, ...groups } })
        } while (this.groupsDirty && epoch === this.epoch && this.state.phase === 'authenticated')
        if (epoch === this.epoch) {
          for (const [roomId, messages] of Object.entries(this.state.messages)) {
            if (!this.state.rooms[Number(roomId)]) {
              const incoming = Object.values(messages).find(message => message.sender_id !== this.state.user?.id)
              if (incoming) void this.openPrivate(incoming.sender_id, false)
            }
          }
        }
      } catch (error) { if (epoch === this.epoch) this.report(error) }
      finally {
        if (epoch === this.epoch) { this.groupFlight = null; this.patch({ groupsLoading: false }) }
      }
    })()
    return this.groupFlight
  }

  selectRoom(id: number) {
    this.selection++
    const unread = { ...this.state.unread }; delete unread[id]
    this.patch({ activeRoom: id, unread, highlight: null, error: this.state.phase === 'authenticated' ? '' : this.state.error })
    const room = this.state.rooms[id]
    if (room && isMember(this.state, room) && !this.state.history[id]?.loaded) void this.loadHistory(id)
  }

  /** Latest page first, then older pages by message ID (keyset, no gaps or repeats). */
  async loadHistory(id: number, older = false) {
    const current = this.state.history[id]
    if (this.state.phase !== 'authenticated' || current?.loading || (older && (!current?.loaded || current.next === null))) return
    const epoch = this.epoch, before = older ? current!.next : null
    this.patch({ history: { ...this.state.history, [id]: { loading: true, loaded: !!current?.loaded, next: current?.next ?? null, failed: false } } })
    try {
      const page = await this.pageRequest(limit => this.transport.request('HISTORY_GET', { room_id: id, limit, ...(before === null ? {} : { before_id: before }) }))
      if (epoch !== this.epoch) return
      this.merge(id, page.messages)
      // Older pages keep moving the cursor back; the latest page sets it the first time.
      const next = older || !current?.loaded ? page.next_before_id : current.next
      this.patch({ history: { ...this.state.history, [id]: { loading: false, loaded: true, next, failed: false } } })
    } catch (error) {
      if (epoch !== this.epoch) return
      this.patch({ history: { ...this.state.history, [id]: { loading: false, loaded: !!current?.loaded, next: current?.next ?? null, failed: true } } })
      this.report(error)
    }
  }
  private merge(room: number, list: Message[]) {
    if (!list.length) return
    const current = { ...(this.state.messages[room] || {}) }
    for (const message of list) current[message.message_id] = message
    this.patch({ messages: { ...this.state.messages, [room]: current } })
  }

  search(room: number, filters: SearchFilters, before: number | null): Promise<Page> {
    if (this.state.phase !== 'authenticated') return Promise.reject(new ClientError('CONNECTION', true))
    return this.pageRequest(limit => this.transport.request('HISTORY_SEARCH', { room_id: room, limit, ...filters, ...(before === null ? {} : { before_id: before }) }), 30)
  }

  /** Open a search result in the transcript, loading older pages until it is there. */
  async jumpTo(room: number, message: number) {
    if (this.state.activeRoom !== room) this.selectRoom(room)
    const epoch = this.epoch
    let pages = 0
    while (!this.state.messages[room]?.[message] && pages < JUMP_PAGES) {
      const history = this.state.history[room]
      if (epoch !== this.epoch || this.state.phase !== 'authenticated' || history?.failed) return
      if (history?.loading) { await new Promise(resolve => setTimeout(resolve, 50)); continue }
      if (history?.loaded && history.next === null) break
      await this.loadHistory(room, !!history?.loaded)
      pages++
    }
    if (epoch !== this.epoch) return
    if (this.state.messages[room]?.[message]) this.patch({ highlight: message })
    else if (this.state.phase === 'authenticated') this.patch({ error: 'ข้อความนี้อยู่ไกลเกินไปในประวัติ ลองค้นด้วยช่วงวันที่ที่แคบลง หรือกดโหลดข้อความก่อนหน้า' })
  }
  /** Group-only AI summary of the latest ≤50 messages this user may read (CP09). */
  async summarize(room: number) {
    if (this.state.phase !== 'authenticated' || this.state.ai[room]?.loading) return
    const epoch = this.epoch, previous = this.state.ai[room]?.result ?? null
    this.patch({ ai: { ...this.state.ai, [room]: { loading: true, error: '', result: previous } } })
    try {
      const result = await this.transport.request('AI_SUMMARIZE', { room_id: room }, AI_TIMEOUT)
      if (epoch === this.epoch) this.patch({ ai: { ...this.state.ai, [room]: { loading: false, error: '', result } } })
    } catch (error) {
      if (epoch === this.epoch) this.patch({ ai: { ...this.state.ai, [room]: { loading: false, error: errorText(error), result: previous } } })
    }
  }
  clearHighlight() { if (this.state.highlight !== null) this.patch({ highlight: null }) }
  private acceptRoom(room: Room, select: boolean) {
    this.patch({ rooms: { ...this.state.rooms, [room.id]: room } })
    if (select) this.selectRoom(room.id)
  }
  async openPrivate(peer: number, select = true) {
    if (this.state.phase !== 'authenticated') return
    const intent = select ? ++this.selection : null
    const existing = this.opening.get(peer)
    if (existing) { if (select) existing.intent = intent; return }
    const pending = { intent }; this.opening.set(peer, pending)
    const epoch = this.epoch
    try {
      const result = await this.transport.request('PRIVATE_ROOM_OPEN', { peer_id: peer })
      if (epoch === this.epoch) this.acceptRoom(result.room, pending.intent !== null && pending.intent === this.selection)
    } catch (error) { if (epoch === this.epoch) this.report(error) }
    finally { if (epoch === this.epoch) this.opening.delete(peer) }
  }
  async createGroup(name: string) {
    const epoch = this.epoch, intent = ++this.selection
    try {
      const result = await this.transport.request('GROUP_CREATE', { name })
      if (epoch === this.epoch) this.acceptRoom(result.room, intent === this.selection)
    } catch (error) { if (epoch === this.epoch) this.report(error) }
  }
  async joinGroup(id: number) {
    const epoch = this.epoch, intent = ++this.selection
    try {
      const result = await this.transport.request('GROUP_JOIN', { room_id: id })
      if (epoch === this.epoch) this.acceptRoom(result.room, intent === this.selection)
    } catch (error) { if (epoch === this.epoch) this.report(error) }
  }

  private transfer(kind: 'uploads' | 'downloads', key: number, value: Transfer | null) {
    this.patch({ [kind]: value === null ? without(this.state[kind], key) : { ...this.state[kind], [key]: value } })
  }
  dismissUpload(room: number) { this.transfer('uploads', room, null) }

  /** FILE_BEGIN -> ordered 32 KiB Base64 chunks (a small window in flight) -> FILE_END. */
  async upload(id: number, file: File) {
    const room = this.state.rooms[id]
    if (this.state.phase !== 'authenticated' || !room || !isMember(this.state, room)) return
    if (this.state.uploads[id] && !this.state.uploads[id].error) return
    const base = { name: file.name, done: 0, size: file.size, error: '' }
    if (file.size > MAX_FILE_BYTES) { this.transfer('uploads', id, { ...base, error: errors.FILE_TOO_LARGE }); return }
    const epoch = this.epoch
    const inflight: Promise<unknown>[] = []
    this.transfer('uploads', id, base)
    try {
      const bytes = new Uint8Array(await file.arrayBuffer())
      if (bytes.length !== file.size || bytes.length > MAX_FILE_BYTES) throw new ClientError('FILE_TOO_LARGE')
      const sha256 = await sha256Hex(bytes)
      if (epoch !== this.epoch) return
      const begin = await this.transport.request('FILE_BEGIN', { room_id: id, name: file.name, size: bytes.length, sha256 }, FILE_TIMEOUT)
      for (let index = 0; index < begin.chunks; index++) {
        const data = toBase64(bytes.subarray(index * begin.chunk_size, (index + 1) * begin.chunk_size))
        inflight.push(handled(this.transport.request('FILE_CHUNK', { transfer_id: begin.transfer_id, index, data }, FILE_TIMEOUT).then(result => {
          if (epoch === this.epoch && this.state.uploads[id]) this.transfer('uploads', id, { ...this.state.uploads[id], done: result.received })
        })))
        if (inflight.length >= UPLOAD_WINDOW) await inflight.shift()
      }
      await Promise.all(inflight)
      const result = await this.transport.request('FILE_END', { transfer_id: begin.transfer_id }, FILE_TIMEOUT)
      if (epoch !== this.epoch) return
      this.addMessage(result.message)
      this.transfer('uploads', id, null)
    } catch (error) {
      if (epoch !== this.epoch) return
      const code = error instanceof ClientError ? error.code : ''
      const text = code === 'INVALID_INPUT' ? errors.FILE_REJECTED : code === 'FILE_TOO_LARGE' ? errors.FILE_TOO_LARGE : errorText(error)
      this.transfer('uploads', id, { ...(this.state.uploads[id] || base), error: text })
    }
  }

  /** FILE_GET chunks by offset, check SHA-256 in the browser, then save locally. */
  async download(attachment: Attachment) {
    if (this.state.phase !== 'authenticated' || (this.state.downloads[attachment.id] && !this.state.downloads[attachment.id].error)) return
    const epoch = this.epoch, key = attachment.id, attempt = ++this.attempts
    this.downloadAttempt.set(key, attempt)
    const current = () => epoch === this.epoch && this.downloadAttempt.get(key) === attempt
    const inflight: Promise<void>[] = []
    this.transfer('downloads', key, { name: attachment.name, done: 0, size: attachment.size, error: '' })
    try {
      const bytes = new Uint8Array(attachment.size)
      const offsets = attachment.size ? Array.from({ length: Math.ceil(attachment.size / DOWNLOAD_CHUNK) }, (_, i) => i * DOWNLOAD_CHUNK) : [0]
      let received = 0
      const fetchAt = async (offset: number) => {
        const chunk = await this.transport.request('FILE_GET', { attachment_id: attachment.id, offset }, FILE_TIMEOUT)
        const data = fromBase64(chunk.data)
        if (chunk.offset !== offset || chunk.size !== attachment.size || chunk.sha256 !== attachment.sha256 || offset + data.length > bytes.length) throw new ClientError('FILE_CORRUPT')
        bytes.set(data, offset)
        received += data.length
        if (current()) this.transfer('downloads', key, { ...this.state.downloads[key], done: received })
      }
      for (const offset of offsets) {
        inflight.push(handled(fetchAt(offset)))
        if (inflight.length >= DOWNLOAD_WINDOW) await inflight.shift()
      }
      await Promise.all(inflight)
      if (received !== attachment.size || await sha256Hex(bytes) !== attachment.sha256) throw new ClientError('FILE_CORRUPT')
      if (!current()) return
      const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>], { type: 'application/octet-stream' }))
      const link = document.createElement('a')
      link.href = url; link.download = attachment.name; link.rel = 'noopener'
      document.body.append(link); link.click(); link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
      this.transfer('downloads', key, null)
    } catch (error) {
      if (current()) this.transfer('downloads', key, { ...this.state.downloads[key], error: errorText(error) })
    }
  }

  private addMessage(message: Message) {
    const current = this.state.messages[message.room_id] || {}
    if (current[message.message_id]) return
    const unread = { ...this.state.unread }
    if (message.room_id !== this.state.activeRoom && message.sender_id !== this.state.user?.id) unread[message.room_id] = (unread[message.room_id] || 0) + 1
    this.patch({ messages: { ...this.state.messages, [message.room_id]: { ...current, [message.message_id]: message } }, unread })
  }
  async send(id: number) {
    const room = this.state.rooms[id], text = this.state.drafts[id] || ''
    if (this.state.phase !== 'authenticated' || !room || !isMember(this.state, room) || this.state.sending[id]) return
    if (!text.trim() || text.includes('\0') || Array.from(text).length > 4000 || new TextEncoder().encode(text).length > 16000) {
      this.patch({ error: 'ข้อความต้องไม่ว่าง และยาวไม่เกิน 4,000 ตัวอักษร / 16,000 bytes' }); return
    }
    const epoch = this.epoch
    const notices = { ...this.state.notices }; delete notices[id]
    this.patch({ sending: { ...this.state.sending, [id]: true }, notices, error: '' })
    try {
      const result = await this.transport.request('MESSAGE_SEND', { room_id: id, text })
      if (epoch !== this.epoch) return
      this.addMessage(result.message)
      if (this.state.drafts[id] === text) this.setDraft(id, '')
    } catch (error) {
      if (epoch === this.epoch) this.patch({ notices: { ...this.state.notices, [id]: error instanceof ClientError && error.network ? uncertain : 'ส่งไม่สำเร็จ ข้อความร่างยังอยู่ กรุณาตรวจแล้วส่งใหม่' }, error: errorText(error) })
    } finally {
      if (epoch === this.epoch) { const sending = { ...this.state.sending }; delete sending[id]; this.patch({ sending }) }
    }
  }

  private event(packet: EventPacket) {
    if (this.state.phase !== 'authenticated') return
    if (packet.type === 'USERS_UPDATED') {
      const data = packet.data as { users: User[]; revision: number }
      if (data.revision > this.revision) { this.revision = data.revision; this.patch({ users: data.users }) }
    } else if (packet.type === 'GROUPS_UPDATED') void this.refreshGroups()
    else {
      const message = packet.data as Message
      this.addMessage(message)
      if (!this.state.rooms[message.room_id]) void this.refreshGroups()
    }
  }
  private disconnected(error: ClientError, intentional: boolean) {
    const notices = { ...this.state.notices }
    for (const room of Object.keys(this.state.sending)) notices[Number(room)] = uncertain
    const cut = (record: Record<number, Transfer>, text: string) => Object.fromEntries(Object.entries(record).map(([key, value]) => [key, value.error ? value : { ...value, error: text }]))
    const history = Object.fromEntries(Object.entries(this.state.history).map(([key, value]) => [key, { ...value, loading: false }]))
    const ai = Object.fromEntries(Object.entries(this.state.ai).map(([key, value]) => [key, value.loading ? { ...value, loading: false, error: errorText(error) } : value]))
    this.patch({ phase: 'disconnected', authBusy: false, users: [], groupsLoading: false, sending: {}, notices, history, ai,
      uploads: cut(this.state.uploads, 'การเชื่อมต่อขาดหาย ไฟล์นี้ยังไม่ถูกส่ง'), downloads: cut(this.state.downloads, 'การเชื่อมต่อขาดหาย ดาวน์โหลดไม่สำเร็จ'),
      error: intentional ? '' : errorText(error) })
  }
  async logout() {
    try { if (this.state.phase === 'authenticated') await this.transport.request('LOGOUT') }
    catch { /* Closing the connection also revokes its server-side session. */ }
    this.close()
    this.state = empty()
    this.patch({ info: 'ออกจากระบบแล้ว' })
  }
  close() { this.epoch++; this.transport.close() }
}
