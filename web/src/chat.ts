import { ClientError, Transport } from './transport'
import type { EventPacket, Message, Room, State, User } from './types'

const empty = (): State => ({ phase: 'disconnected', authBusy: false, user: null, users: [], rooms: {}, messages: {}, drafts: {}, unread: {}, notices: {}, sending: {}, activeRoom: null, groupsLoading: false, error: '', info: '' })
const errors: Record<string, string> = {
  AUTH_FAILED: 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', USERNAME_TAKEN: 'ชื่อผู้ใช้นี้ถูกใช้แล้ว กรุณาเลือกชื่อใหม่',
  ALREADY_LOGGED_IN: 'บัญชีนี้เข้าสู่ระบบอยู่แล้ว กรุณาออกจากระบบที่เครื่องเดิมก่อน',
  RATE_LIMITED: 'ลองบ่อยเกินไป กรุณารอสักครู่แล้วลองใหม่', AUTH_REQUIRED: 'กรุณาเข้าสู่ระบบใหม่',
  FORBIDDEN: 'คุณยังไม่มีสิทธิ์ใช้งานห้องนี้', INVALID_INPUT: 'ข้อมูลไม่ถูกต้อง กรุณาตรวจชื่อ รหัสผ่าน หรือความยาวข้อความ',
  FRAME_TOO_LARGE: 'ข้อมูลมีขนาดใหญ่เกินไป กรุณาลองโหลดใหม่',
  CONNECTION: 'การเชื่อมต่อขาดหาย หรือเชื่อมต่อ Server ไม่ได้', TIMEOUT: 'Server ไม่ตอบกลับภายในเวลาที่กำหนด',
  PROTOCOL: 'ข้อมูลการเชื่อมต่อไม่สมบูรณ์ กรุณาเข้าสู่ระบบใหม่', BUSY: 'กำลังทำหลายรายการ กรุณารอสักครู่',
}
export function errorText(error: unknown) { return error instanceof ClientError ? errors[error.code] || 'ทำรายการไม่สำเร็จ กรุณาลองใหม่' : 'ทำรายการไม่สำเร็จ กรุณาลองใหม่' }
export function isMember(state: State, room: Room) { return room.members.some(member => member.id === state.user?.id) }
export function roomTitle(state: State, room: Room) { return room.kind === 'group' ? room.name! : room.members.find(member => member.id !== state.user?.id)?.username || 'แชตส่วนตัว' }
const uncertain = 'ยังยืนยันการส่งไม่ได้ ข้อความอาจถูกบันทึกแล้ว เก็บร่างไว้ให้ตรวจสอบก่อนส่งใหม่'

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
      this.state = retained
      this.patch({ user: result.user, authBusy: false, phase: 'authenticated', users: [], error: '', info: '' })
      void this.loadUsers(epoch)
      void this.refreshGroups()
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
    this.patch({ activeRoom: id, unread, error: this.state.phase === 'authenticated' ? '' : this.state.error })
  }
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
    this.patch({ phase: 'disconnected', authBusy: false, users: [], groupsLoading: false, sending: {}, notices, error: intentional ? '' : errorText(error) })
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
