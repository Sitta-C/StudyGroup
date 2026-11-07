import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { CSSProperties, FormEvent, ReactNode } from 'react'
import { ArrowRight, CalendarDays, Check, ChevronRight, Compass, Download, ListChecks, RefreshCw, MessageCircle, Handshake, FileText, LockKeyhole, LogOut, Menu, MessageSquare, Paperclip, Plus, Search, Settings2, Sparkles, Users, Wifi, WifiOff, X } from 'lucide-react'
import { ChatController, errorText, isMember, roomTitle } from './chat'
import type { SearchFilters } from './chat'
import { formatSize, localDayRange, MAX_FILE_BYTES } from './files'
import { SESSION_STORAGE_KEY } from './session'
import type { Attachment, Message, Room, State, Transfer } from './types'

const control = new ChatController()
const PORTRAIT_COUNT = 6
function Avatar({ name, own = false, online = false, portrait }: { name: string; own?: boolean; online?: boolean; portrait?: number }) {
  // A stable presentation fallback, shared across rooms; no profile data is changed.
  const hash = Array.from(name.toLowerCase()).reduce((value, char) => Math.imul(value ^ char.codePointAt(0)!, 16777619) >>> 0, 2166136261)
  const index = portrait ?? ((hash ^ (hash >>> 16)) >>> 0) % PORTRAIT_COUNT
  const ring = ['#68785c', '#796052', '#5c7285', '#80647d', '#8b713d', '#5c7a77'][(hash >>> 8) % 6]
  return <span className={`ss-avatar ss-portrait-${index}${own ? ' ss-self' : ''}`} style={{ '--avatar-ring': ring } as CSSProperties} aria-hidden="true"><span className="ss-portrait" />{portrait === undefined && <b className="ss-avatar-initials">{name.slice(0, 2).toUpperCase()}</b>}{online && <span className="ss-online-dot" />}</span>
}
function Brand() { return <div className="ss-brand" aria-label="StudyGroup">studygroup<span>.</span></div> }

function Auth({ state }: { state: State }) {
  const [register, setRegister] = useState(false)
  const [username, setUsername] = useState(state.user?.username || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  useEffect(() => { if (state.info.startsWith('สมัครสมาชิก')) setRegister(false) }, [state.info])
  function submit(event: FormEvent) {
    event.preventDefault()
    void control.authenticate(register, username, password, confirm)
    setPassword(''); setConfirm('')
  }
  return <main className="ss-auth"><aside className="ss-auth-intro" aria-label="เกี่ยวกับ StudyGroup"><span className="ss-eyebrow">STUDYGROUP / QUIET CLUB</span><h2>A little focus.<br />A good team.</h2><p>พื้นที่เรียบง่าย สำหรับคุยงานกับทีมของคุณ</p><div className="ss-auth-portraits" aria-hidden="true">{[0, 1, 2].map(portrait => <Avatar key={portrait} name="" portrait={portrait} />)}</div></aside><div className="ss-auth-form-area"><section className="ss-auth-card">
    <Brand />
    <p className="ss-eyebrow">{register ? 'JOIN THE TEAM' : 'WELCOME BACK'}</p>
    <div className="ss-auth-heading"><h1>{register ? 'สร้างบัญชีของคุณ' : 'ยินดีต้อนรับกลับมา'}</h1><p>{register ? 'เริ่มคุยงานกับทีมใน StudyGroup' : 'เข้าสู่ระบบเพื่อกลับไปคุยงานกับทีม'}</p></div>
    <form onSubmit={submit}>
      <label className="ss-field">ชื่อผู้ใช้<input name="username" autoComplete="username" className="ss-input" value={username} onChange={e => setUsername(e.target.value)} required pattern="[A-Za-z0-9_]{3,24}" maxLength={24} disabled={state.authBusy} autoFocus /></label>
      <p className="ss-small ss-field-hint">ตัวอักษรอังกฤษ ตัวเลข และ _ จำนวน 3–24 ตัว</p>
      <label className="ss-field">รหัสผ่าน<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} className="ss-input" value={password} onChange={e => setPassword(e.target.value)} required disabled={state.authBusy} /></label>
      {register && <><label className="ss-field">ยืนยันรหัสผ่าน<input name="confirm-password" type="password" autoComplete="new-password" className="ss-input" value={confirm} onChange={e => setConfirm(e.target.value)} required disabled={state.authBusy} /></label><p className="ss-small ss-field-hint">รหัสผ่าน 8–128 ตัวอักษร</p></>}
      {state.error && <p className="ss-error" role="alert">{state.error}</p>}
      {state.info && <p className="ss-success" role="status">{state.info}</p>}
      <button className="ss-btn ss-primary ss-auth-submit" disabled={state.authBusy}>{state.authBusy ? 'กำลังเชื่อมต่อ…' : register ? 'สมัครสมาชิก' : 'เข้าสู่ระบบ'}</button>
    </form>
    <button className="ss-auth-switch" disabled={state.authBusy} onClick={() => { setRegister(!register); setPassword(''); setConfirm(''); control.clearError() }}>{register ? 'มีบัญชีแล้ว? เข้าสู่ระบบ' : 'ยังไม่มีบัญชี? สมัครสมาชิก'}</button>
    <div className="ss-auth-note"><LockKeyhole size={13} /> ใช้บัญชี StudyGroup เพื่อกลับมาคุยกับทีม</div>
  </section></div></main>
}

function Modal({ title, children, close, className = '', closeLabel = 'ปิดหน้าต่าง', returnFocus }: { title: string; children: ReactNode; close: () => void; className?: string; closeLabel?: string; returnFocus?: string }) {
  const ref = useRef<HTMLDialogElement>(null)
  const opener = useRef(document.activeElement as HTMLElement | null)
  const titleId = useRef(`dialog-${crypto.getRandomValues(new Uint32Array(1))[0]}`)
  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    dialog.querySelector<HTMLElement>('[data-dialog-focus]')?.focus()
    return () => {
      dialog.close()
      const target = returnFocus ? document.querySelector<HTMLElement>(returnFocus) : opener.current
      if (target?.isConnected) target.focus({ preventScroll: true })
    }
  }, [returnFocus])
  return <dialog className={`ss-modal ${className}`} ref={ref} aria-labelledby={titleId.current} onCancel={event => { event.preventDefault(); close() }} onClick={event => { if (event.target === ref.current) { const bounds = ref.current.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close() } }}>
    <div className="ss-modal-head"><h2 id={titleId.current}>{title}</h2><button className="ss-icon" onClick={close} aria-label={closeLabel}><X /></button></div>{children}
  </dialog>
}

function GroupForm({ close }: { close: () => void }) {
  const [name, setName] = useState('')
  return <form onSubmit={event => { event.preventDefault(); void control.createGroup(name); close() }}>
    <p className="ss-small">เริ่มจากคุณคนเดียว เพื่อนเลือกเข้าร่วมได้เอง</p>
    <label className="ss-field">ชื่อกลุ่ม<input className="ss-input" autoFocus data-dialog-focus required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
    <div className="ss-modal-actions"><button type="button" className="ss-btn" onClick={close}>ยกเลิก</button><button className="ss-btn ss-primary" disabled={!name.trim()}><Plus /> สร้างกลุ่ม</button></div>
  </form>
}

function Directory({ state, close }: { state: State; close: () => void }) {
  const groups = Object.values(state.rooms).filter(room => room.kind === 'group')
  useEffect(() => { void control.refreshGroups() }, [])
  return <div className="ss-directory"><p className="ss-small">{groups.length} กลุ่ม · เห็นรายชื่อสมาชิกก่อนเข้าร่วม</p>
    {groups.map(room => <div className="ss-dir-card" key={room.id}><span className="ss-roomicon">#</span><div className="ss-label"><strong>{room.name}</strong><p className="ss-small">สมาชิก: {room.members.map(member => member.username).join(', ')}</p></div><button className={`ss-btn ${isMember(state, room) ? '' : 'ss-primary'}`} disabled={state.phase !== 'authenticated'} onClick={() => { if (isMember(state, room)) control.selectRoom(room.id); else void control.joinGroup(room.id); close() }}>{isMember(state, room) ? 'เปิดห้อง' : 'เข้าร่วม'}</button></div>)}
    {!groups.length && <p className="ss-empty">{state.groupsLoading ? 'กำลังโหลดกลุ่ม…' : 'ยังไม่มีกลุ่ม เริ่มสร้างกลุ่มของทีมคุณได้เลย'}</p>}
  </div>
}

function Sidebar({ state, create, directory, connection, mobile, close }: { state: State; create: () => void; directory: () => void; connection: () => void; mobile: boolean; close: () => void }) {
  const [menu, setMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const navRef = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!mobile) return
    const before = document.activeElement as HTMLElement | null
    const nav = navRef.current!
    nav.querySelector<HTMLButtonElement>('.ss-nav-close')?.focus()
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); close() }
      if (event.key !== 'Tab') return
      const buttons = Array.from(nav.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
      const first = buttons[0], last = buttons.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    nav.addEventListener('keydown', keyboard)
    return () => { nav.removeEventListener('keydown', keyboard); before?.focus() }
  }, [mobile, close])
  useEffect(() => {
    if (!menu) return
    const outside = (event: PointerEvent) => { if (!menuRef.current?.contains(event.target as Node)) setMenu(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenu(false) }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [menu])
  const online = state.phase === 'authenticated'
  const privateRooms = Object.values(state.rooms).filter(room => room.kind === 'private')
  const roomForPeer = (id: number) => privateRooms.find(room => room.members.some(member => member.id === id))
  const groups = Object.values(state.rooms).filter(room => room.kind === 'group')
  return <>
    {mobile && <button className="ss-nav-scrim" onClick={close} aria-label="ปิดรายชื่อห้อง" />}
    <nav id="room-navigation" ref={navRef} className={`ss-sidebar ${mobile ? 'is-open' : ''}`} aria-label="รายชื่อคนและห้องแชต">
      <div className="ss-sidebar-head"><Brand /><button className="ss-icon ss-nav-close" onClick={close} aria-label="ปิดเมนูห้อง"><X /></button></div>
      <div className="ss-sidebar-scroll">
        <section><div className="ss-section-title"><strong>ห้องกลุ่ม</strong><button className="ss-icon" onClick={create} disabled={!online} aria-label="สร้างกลุ่มใหม่" title="สร้างกลุ่มใหม่"><Plus /></button></div>
          {groups.map(room => <button className={`ss-room${state.activeRoom === room.id ? ' is-active' : ''}`} key={room.id} onClick={() => { control.selectRoom(room.id); close() }} aria-current={state.activeRoom === room.id ? 'page' : undefined} aria-label={`เปิดห้อง ${room.name}`} title={`${room.name}\n${room.members.map(member => member.username).join(', ')}`}><span className="ss-roomicon">#</span><span className="ss-label"><span className="ss-name">{room.name}</span><span className="ss-small ss-row-detail">{room.members.map(member => member.username).join(', ')}</span></span>{state.activeRoom === room.id && <Check className="ss-current-marker" aria-hidden="true" />}{!isMember(state, room) ? <span className="ss-badge">เข้าร่วม</span> : !!state.unread[room.id] && <span className="ss-unread">{state.unread[room.id]}</span>}</button>)}
          <button className="ss-link" onClick={directory}><Compass size={14} /> สำรวจกลุ่มทั้งหมด</button>
          {state.groupsLoading && <span className="ss-small ss-loading" role="status">กำลังโหลดกลุ่ม…</span>}
        </section>
        <section aria-label="แชตส่วนตัว"><div className="ss-section-title"><strong>แชตส่วนตัว</strong></div>
          {privateRooms.map(room => { const name = roomTitle(state, room), present = online && state.users.some(user => user.id !== state.user!.id && room.members.some(member => member.id === user.id)); return <button className={`ss-person${room.id === state.activeRoom ? ' is-active' : ''}`} key={room.id} aria-label={`แชตส่วนตัวกับ ${name}`} aria-current={room.id === state.activeRoom ? 'page' : undefined} onClick={() => { control.selectRoom(room.id); close() }}><Avatar name={name} online={present} /><span className="ss-label"><span className="ss-name">{name}</span><span className="ss-small ss-row-detail">{present ? 'ออนไลน์' : 'ออฟไลน์'}</span></span>{room.id === state.activeRoom && <Check className="ss-current-marker" aria-hidden="true" />}{!!state.unread[room.id] && <span className="ss-unread">{state.unread[room.id]}</span>}</button> })}
          {!privateRooms.length && <p className="ss-small ss-list-empty">เลือกเพื่อนออนไลน์เพื่อเริ่มคุย</p>}
        </section>
        <section><div className="ss-section-title"><strong>ออนไลน์</strong><span>{state.users.length} คน</span></div>
          {state.users.filter(user => user.id === state.user!.id || !roomForPeer(user.id)).map(user => { const own = user.id === state.user!.id; return <button className="ss-person" key={user.id} onClick={() => { if (own) setMenu(!menu); else { void control.openPrivate(user.id); close() } }} aria-label={own ? `บัญชี ${user.username}` : `แชตส่วนตัวกับ ${user.username}`}>
            <Avatar name={user.username} own={own} online /><span className="ss-label"><span className="ss-name">{user.username}{own && <span className="ss-small"> (คุณ)</span>}</span><span className="ss-small ss-row-detail">{own ? 'พร้อมคุยงาน' : 'ส่งข้อความส่วนตัว'}</span></span>
          </button> })}
          {!state.users.length && <p className="ss-small ss-list-empty">{online ? 'กำลังโหลดรายชื่อ…' : 'ขาดการเชื่อมต่อ'}</p>}
        </section>


      </div>
      <div className="ss-sidebar-bottom"><button className={`ss-connection${online ? '' : ' is-offline'}`} onClick={connection}><span />{online ? 'เชื่อมต่อแล้ว' : 'ขาดการเชื่อมต่อ'}<ChevronRight size={14} /></button>
        <div className="ss-account-wrap" ref={menuRef}><button className="ss-account" onClick={() => setMenu(!menu)} aria-expanded={menu} aria-label="เมนูบัญชี"><Avatar name={state.user!.username} own /><span className="ss-label"><span className="ss-name">{state.user!.username}</span><span className="ss-small ss-row-detail">บัญชีของคุณ</span></span><Settings2 size={17} /></button>
          {menu && <div className="ss-account-menu"><button onClick={() => { setMenu(false); connection() }}><Wifi size={15} /> การเชื่อมต่อ</button><button onClick={() => { setMenu(false); void control.logout() }}><LogOut size={15} /> ออกจากระบบ</button></div>}
        </div>
      </div>
    </nav>
  </>
}

function dayLabel(date: Date) {
  const day = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
  return date.toDateString() === new Date().toDateString() ? `วันนี้ · ${day}` : day
}
const timeFormat = new Intl.DateTimeFormat('th-TH', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const dateTimeFormat = new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const UNSPECIFIED = 'ไม่ระบุ'
const percent = (transfer: Transfer) => transfer.size ? Math.min(100, Math.floor(transfer.done * 100 / transfer.size)) : 100
const senderName = (state: State, room: Room, id: number) => id === state.user!.id ? 'คุณ' : room.members.find(member => member.id === id)?.username || `ผู้ใช้ ${id}`

function DownloadButton({ state, attachment }: { state: State; attachment: Attachment }) {
  const download = state.downloads[attachment.id], busy = !!download && !download.error
  return <>
    <button className="ss-file-download" onClick={() => void control.download(attachment)} disabled={state.phase !== 'authenticated' || busy} aria-label={`ดาวน์โหลด ${attachment.name}`} title={`ดาวน์โหลด ${attachment.name}`}>{busy ? `${percent(download)}%` : <Download />}</button>
    {busy && <progress className="ss-progress" max={100} value={percent(download)} aria-label={`กำลังดาวน์โหลด ${attachment.name}`} />}
    {download?.error && <span className="ss-file-error" role="alert">{download.error}</span>}
  </>
}

function FileCard({ state, attachment }: { state: State; attachment: Attachment }) {
  return <div className="ss-bubble ss-file-card">
    <span className="ss-file-icon"><FileText /></span>
    <span className="ss-file-info"><span className="ss-file-name">{attachment.name}</span><span className="ss-file-size">{formatSize(attachment.size)}</span></span>
    <DownloadButton state={state} attachment={attachment} />
  </div>
}

function Transcript({ state, room }: { state: State; room: Room }) {
  const ref = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)
  const previous = useRef<number | null>(null)
  const anchor = useRef<{ first?: number; height: number }>({ height: 0 })
  // Keep a reading anchor independently of scroll events caused by panel resizing.
  const viewport = useRef<{ height: number; width: number; scrollTop: number; message?: string; offset: number }>({ height: 0, width: 0, scrollTop: 0, offset: 0 })
  const rememberPosition = useCallback(() => {
    const element = ref.current
    if (!element) return
    const top = element.getBoundingClientRect().top
    const visible = Array.from(element.querySelectorAll<HTMLElement>('[data-message-id]')).find(item => item.getBoundingClientRect().bottom > top)
    viewport.current = { height: element.clientHeight, width: element.clientWidth, scrollTop: element.scrollTop, message: visible?.dataset.messageId, offset: visible ? visible.getBoundingClientRect().top - top : 0 }
    nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 70
  }, [])
  useLayoutEffect(() => {
    const element = ref.current!
    const observer = new ResizeObserver(() => {
      if (element.clientHeight === viewport.current.height && element.clientWidth === viewport.current.width) return
      if (nearBottom.current) element.scrollTop = element.scrollHeight
      else if (viewport.current.message) {
        const item = element.querySelector<HTMLElement>(`[data-message-id="${viewport.current.message}"]`)
        if (item) element.scrollTop += item.getBoundingClientRect().top - element.getBoundingClientRect().top - viewport.current.offset
      }
      rememberPosition()
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [rememberPosition])
  const messages = Object.values(state.messages[room.id] || {}).sort((a, b) => a.message_id - b.message_id)
  const last = messages.at(-1), first = messages[0]?.message_id
  const history = state.history[room.id]
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const changed = previous.current !== room.id, before = anchor.current
    if (!changed && before.first !== undefined && first !== undefined && first < before.first) element.scrollTop += element.scrollHeight - before.height
    else if (changed || nearBottom.current || last?.sender_id === state.user!.id) element.scrollTop = element.scrollHeight
    previous.current = room.id
    anchor.current = { first, height: element.scrollHeight }
    rememberPosition()
  }, [room.id, messages.length, first, last?.message_id, state.user])
  useEffect(() => {
    if (state.highlight === null) return
    ref.current?.querySelector(`[data-message-id="${state.highlight}"]`)?.scrollIntoView({ block: 'center' })
    const timer = setTimeout(() => control.clearHighlight(), 2500)
    return () => clearTimeout(timer)
  }, [state.highlight])
  let previousDate = ''
  return <div className="ss-chat-body" ref={ref} onScroll={() => {
    const element = ref.current!
    // A real scroll before the resize callback takes priority over the old pinned position.
    if (element.clientHeight === viewport.current.height || element.scrollTop !== viewport.current.scrollTop) rememberPosition()
  }} role="log" aria-label="ข้อความในห้อง" aria-live="polite" aria-relevant="additions" aria-busy={!!history?.loading}>
    <div className="ss-history-edge">
      {history?.loading ? <span className="ss-small" role="status">กำลังโหลดประวัติ…</span>
        : history?.failed ? <button className="ss-link" onClick={() => void control.loadHistory(room.id, history.loaded)}>โหลดประวัติไม่สำเร็จ · ลองใหม่</button>
          : history?.loaded && history.next !== null ? <button className="ss-btn ss-history-more" onClick={() => void control.loadHistory(room.id, true)} disabled={state.phase !== 'authenticated'}>โหลดข้อความก่อนหน้า</button>
            : history?.loaded && messages.length ? <span className="ss-small">จุดเริ่มต้นประวัติที่คุณเห็นได้ในห้องนี้</span> : null}
    </div>
    {!messages.length && !history?.loading && <div className="ss-empty"><MessageSquare /><p>ยังไม่มีข้อความในห้องนี้</p><span className="ss-small">{room.kind === 'group' && room.created_by !== state.user!.id ? 'คุณจะเห็นข้อความตั้งแต่ตอนที่เข้าร่วมกลุ่มเป็นต้นไป' : 'ข้อความจะถูกบันทึกไว้ เปิดแอปใหม่ก็ยังเห็นได้'}</span></div>}
    {messages.map((message, index) => {
      const date = new Date(message.created_at), key = date.toDateString(), showDay = key !== previousDate
      previousDate = key
      const own = message.sender_id === state.user!.id
      const sender = senderName(state, room, message.sender_id)
      const before = messages[index - 1]
      const continued = !showDay && before?.sender_id === message.sender_id && date.getTime() - new Date(before.created_at).getTime() >= 0 && date.getTime() - new Date(before.created_at).getTime() <= 5 * 60 * 1000
      return <div className={`ss-message-item${continued ? ' ss-continuation' : ''}`} key={message.message_id}>{showDay && <div className="ss-day"><span>{dayLabel(date)}</span></div>}<article className={`ss-message ${own ? 'ss-mine' : ''}${state.highlight === message.message_id ? ' is-highlighted' : ''}`} data-message-id={message.message_id} title={`${sender} · ${dateTimeFormat.format(date)}`}>
        {continued ? <span className="ss-avatar-space" aria-hidden="true" /> : <Avatar name={own ? state.user!.username : sender} own={own} />}
        <div className="ss-message-body"><div className={`ss-message-meta${continued ? ' ss-sr-only' : ''}`}><span>{sender}</span><time dateTime={message.created_at}>{timeFormat.format(date)}</time></div>{message.attachment ? <FileCard state={state} attachment={message.attachment} /> : <p className="ss-bubble">{message.text}</p>}</div>
      </article></div>
    })}
  </div>
}

function FilesPanel({ state, room }: { state: State; room: Room }) {
  const [files, setFiles] = useState<Message[]>([])
  const [next, setNext] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const sequence = useRef(0)
  const online = state.phase === 'authenticated'
  async function load(before: number | null) {
    const id = ++sequence.current
    setLoading(true); setError('')
    try {
      const page = await control.search(room.id, { kind: 'file' }, before)
      if (id !== sequence.current) return
      setFiles(old => before === null ? page.messages : [...old, ...page.messages]); setNext(page.next_before_id)
    } catch (failure) { if (id === sequence.current) setError(errorText(failure)) }
    finally { if (id === sequence.current) setLoading(false) }
  }
  useEffect(() => { setFiles([]); setNext(null); if (online) void load(null) }, [room.id, online])
  const all = [...new Map([...files, ...Object.values(state.messages[room.id] || {}).filter(message => message.attachment)].map(message => [message.message_id, message])).values()].sort((a, b) => b.message_id - a.message_id)
  return <div className="ss-chat-body ss-files" aria-label="ไฟล์ในห้อง" aria-busy={loading}>
    <p className="ss-small">ไฟล์ที่แชร์ในห้องนี้ · ไม่เกิน {formatSize(MAX_FILE_BYTES)} ต่อไฟล์</p>
    {all.map(message => <div className="ss-file-row" key={message.message_id}>
      <span className="ss-file-icon"><FileText /></span>
      <div className="ss-file-info"><span className="ss-file-name">{message.attachment!.name}</span><span className="ss-small">{senderName(state, room, message.sender_id)} · {dateTimeFormat.format(new Date(message.created_at))} · {formatSize(message.attachment!.size)}</span><details className="ss-file-details"><summary>รายละเอียดไฟล์</summary><p>ตรวจสอบความถูกต้องของไฟล์ทุกครั้งที่ดาวน์โหลด</p><p>SHA-256 <code>{message.attachment!.sha256}</code></p></details></div>
      <DownloadButton state={state} attachment={message.attachment!} />
    </div>)}
    {loading && <p className="ss-small" role="status">กำลังโหลดรายการไฟล์…</p>}
    {error && <p className="ss-error" role="alert">{error}</p>}
    {!loading && !error && !all.length && <div className="ss-empty"><FileText /><p>ยังไม่มีไฟล์ในห้องนี้</p><span className="ss-small">กดรูปคลิปในช่องพิมพ์เพื่อส่งไฟล์ให้สมาชิกในห้อง</span></div>}
    {!loading && next !== null && <button className="ss-btn ss-history-more" onClick={() => void load(next)} disabled={!online}>โหลดไฟล์ก่อนหน้า</button>}
  </div>
}

function AIPanel({ state, room, close }: { state: State; room: Room; close: () => void }) {
  const ai = state.ai[room.id], result = ai?.result, summary = result?.summary
  const none = <p className="ss-small">{UNSPECIFIED}</p>
  return <aside className="ss-insight" aria-label="ผู้ช่วยสรุปบทสนทนา" aria-busy={!!ai?.loading}>
    <div className="ss-insight-head"><span className="ss-ai-title"><Sparkles /> สรุปด้วย AI</span><button className="ss-icon" onClick={close} aria-label="ปิดสรุป AI"><X /></button></div>
    <p className="ss-ai-note">{result ? `ห้อง ${room.name} · ${result.message_count} ข้อความล่าสุดที่คุณเห็นได้ · ${timeFormat.format(new Date(result.generated_at))}` : 'เฉพาะบทสนทนาในห้องนี้ ไม่เกิน 50 ข้อความล่าสุด'}</p>
    {ai?.loading && <p className="ss-small" role="status">กำลังให้ AI สรุปบทสนทนา…</p>}
    {ai?.error && <p className="ss-error" role="alert">{ai.error}</p>}
    {summary && (result!.message_count === 0 ? <p className="ss-small">ยังไม่มีข้อความที่คุณเห็นได้ให้สรุป</p> : <div className="ss-summary-grid" aria-live="polite">
      <section className="ss-summary-section"><h3><MessageCircle /> ประเด็นสำคัญ</h3>{summary.topics.length ? <ul>{summary.topics.map((item, i) => <li key={i}>{item}</li>)}</ul> : none}</section>
      <section className="ss-summary-section"><h3><Handshake /> ข้อตกลง</h3>{summary.agreements.length ? <ul>{summary.agreements.map((item, i) => <li key={i}>{item}</li>)}</ul> : none}</section>
      <section className="ss-summary-section"><h3><ListChecks /> งานและผู้รับผิดชอบ</h3>{summary.tasks.length ? <ul className="ss-task-list">{summary.tasks.map((task, i) => <li key={i}><span>{task.task}</span><span className="ss-task-meta">{task.owner} · กำหนดส่ง {task.due}</span></li>)}</ul> : none}</section>
      <section className="ss-summary-section"><h3><CalendarDays /> กำหนดส่ง</h3>{summary.deadlines.length ? <ul className="ss-task-list">{summary.deadlines.map((item, i) => <li key={i}><span>{item.due}</span><span className="ss-task-meta">{item.item}</span></li>)}</ul> : none}</section>
    </div>)}
    <div className="ss-summary-foot"><button className="ss-btn ss-ai" onClick={() => void control.summarize(room.id)} disabled={state.phase !== 'authenticated' || !!ai?.loading}><RefreshCw /> {result ? 'สรุปอีกครั้ง' : 'สรุปบทสนทนา'}</button><span className={`ss-ai-disclaimer${result?.mock ? ' is-mock' : ''}`}>{result?.mock ? 'ผลจำลอง (Mock) สำหรับทดสอบ · ไม่ได้เรียก AI จริง' : result ? `สรุปโดย AI (${result.model}) · อาจคลาดเคลื่อน ควรตรวจสอบก่อนใช้ · เห็นเฉพาะคุณ` : 'ผลสรุปเห็นเฉพาะคุณ ไม่ส่งเข้าห้อง'}</span></div>
  </aside>
}

function snippet(text: string, query: string) {
  if (text.length <= 240) return text
  const at = Math.max(0, text.toLowerCase().indexOf(query.toLowerCase()) - 60)
  return (at ? '…' : '') + text.slice(at, at + 240) + (at + 240 < text.length ? '…' : '')
}
function Highlighted({ text, query }: { text: string; query: string }) {
  const shown = snippet(text, query)
  if (!query) return <>{shown}</>
  const lower = shown.toLowerCase(), needle = query.toLowerCase(), parts: ReactNode[] = []
  let index = 0, found = lower.indexOf(needle)
  while (found !== -1) {
    parts.push(shown.slice(index, found), <mark key={found}>{shown.slice(found, found + needle.length)}</mark>)
    index = found + needle.length; found = lower.indexOf(needle, index)
  }
  parts.push(shown.slice(index))
  return <>{parts}</>
}

function SearchPanel({ state, room, close }: { state: State; room: Room; close: () => void }) {
  const [query, setQuery] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [datesOpen, setDatesOpen] = useState(false)
  const [results, setResults] = useState<Message[] | null>(null)
  const [next, setNext] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const sequence = useRef(0), active = useRef<SearchFilters>({}), term = useRef('')
  async function run(before: number | null) {
    if (before === null) {
      const text = query.trim()
      if (!text && !from && !to) { setError('พิมพ์คำค้นหรือเลือกวันที่อย่างน้อยหนึ่งช่อง'); return }
      if (Array.from(text).length > 200) { setError('คำค้นยาวได้ไม่เกิน 200 ตัวอักษร'); return }
      if (from && to && from > to) { setError('วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด'); return }
      active.current = { ...(text ? { query: text } : {}), ...localDayRange(from, to) }
      term.current = text
    }
    const id = ++sequence.current
    setLoading(true); setError('')
    try {
      const page = await control.search(room.id, active.current, before)
      if (id !== sequence.current) return
      setResults(old => before === null ? page.messages : [...(old || []), ...page.messages]); setNext(page.next_before_id)
    } catch (failure) { if (id === sequence.current) setError(errorText(failure)) }
    finally { if (id === sequence.current) setLoading(false) }
  }
  return <div className="ss-search">
    <form onSubmit={event => { event.preventDefault(); void run(null) }}>
      <label className="ss-field">คำค้น<input className="ss-input" type="search" autoFocus data-dialog-focus maxLength={200} value={query} onChange={event => setQuery(event.target.value)} placeholder="เช่น กำหนดส่ง หรือชื่อไฟล์" /></label>
      <button type="button" className="ss-date-toggle" aria-expanded={datesOpen} aria-controls="search-dates" onClick={() => setDatesOpen(!datesOpen)}><CalendarDays /> กรองตามวันที่{(from || to) && <span> · {from || 'เริ่มต้น'} — {to || 'วันนี้'}</span>}</button>
      <div id="search-dates" hidden={!datesOpen}>
      <div className="ss-date-range">
        <label className="ss-field">ตั้งแต่วันที่<input className="ss-input" type="date" value={from} max={to || undefined} onChange={event => setFrom(event.target.value)} /></label>
        <label className="ss-field">ถึงวันที่<input className="ss-input" type="date" value={to} min={from || undefined} onChange={event => setTo(event.target.value)} /></label>
      </div>
      <p className="ss-small ss-field-hint">วันที่ตามเวลาในเครื่องของคุณ ({Intl.DateTimeFormat().resolvedOptions().timeZone}) · ค้นเฉพาะข้อความที่คุณมีสิทธิ์เห็น</p>
      </div>
      <div className="ss-modal-actions"><button type="button" className="ss-btn" onClick={() => { setQuery(''); setFrom(''); setTo(''); setDatesOpen(false); setResults(null); setError(''); sequence.current++ ; setLoading(false) }}>ล้าง</button><button className="ss-btn ss-primary" disabled={state.phase !== 'authenticated'}><Search /> ค้นหา</button></div>
    </form>
    {error && <p className="ss-error" role="alert">{error}</p>}
    {loading && <p className="ss-small" role="status">กำลังค้นหา…</p>}
    {results && <div className="ss-results" aria-label="ผลการค้นหา">
      {!loading && <p className="ss-small">{results.length ? `พบ ${results.length}${next !== null ? '+' : ''} ข้อความ · ใหม่ไปเก่า` : 'ไม่พบข้อความที่ตรงกับเงื่อนไข'}</p>}
      {results.map(message => <button className="ss-result" key={message.message_id} onClick={() => { close(); void control.jumpTo(room.id, message.message_id) }}>
        <span className="ss-result-meta"><strong>{senderName(state, room, message.sender_id)}</strong><time dateTime={message.created_at}>{dateTimeFormat.format(new Date(message.created_at))}</time></span>
        <span className="ss-result-text">{message.attachment ? <><FileText size={13} /> <Highlighted text={message.attachment.name} query={term.current} /></> : <Highlighted text={message.text || ''} query={term.current} />}</span>
      </button>)}
      {!loading && next !== null && <button className="ss-btn ss-history-more" onClick={() => void run(next)}>โหลดผลเพิ่ม</button>}
    </div>}
  </div>
}

function Composer({ state, room }: { state: State; room: Room }) {
  const draft = state.drafts[room.id] || ''
  const textarea = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const [composing, setComposing] = useState(false)
  const online = state.phase === 'authenticated', upload = state.uploads[room.id], uploading = !!upload && !upload.error
  useEffect(() => { textarea.current?.focus() }, [room.id])
  return <div className="ss-compose-wrap">
    {upload && <div className={`ss-upload${upload.error ? ' is-error' : ''}`} role={upload.error ? 'alert' : 'status'}>
      <Paperclip size={14} /><span className="ss-upload-name">{upload.name}</span>
      {upload.error ? <span className="ss-upload-text">{upload.error}</span> : <><progress className="ss-progress" max={100} value={percent(upload)} aria-label={`กำลังส่งไฟล์ ${upload.name}`} /><span className="ss-upload-text">{upload.done ? `${percent(upload)}%` : 'กำลังเตรียมไฟล์…'}</span></>}
      {upload.error && <button className="ss-icon" onClick={() => control.dismissUpload(room.id)} aria-label="ปิดข้อความแจ้งไฟล์"><X size={14} /></button>}
    </div>}
    <div className="ss-compose">
    <textarea ref={textarea} rows={1} aria-label="ข้อความแชต" placeholder={room.kind === 'group' ? 'พิมพ์ข้อความถึงทีม…' : `พิมพ์ข้อความถึง ${roomTitle(state, room)}…`} value={draft} onChange={event => control.setDraft(room.id, event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={() => setComposing(false)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !composing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); void control.send(room.id) } }} />
    <div className="ss-compose-toolbar"><div className="ss-compose-tools"><input ref={picker} type="file" hidden aria-label="เลือกไฟล์แนบ" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void control.upload(room.id, file) }} /><button className="ss-icon" onClick={() => picker.current?.click()} disabled={!online || uploading} aria-label="แนบไฟล์" title={`แนบไฟล์ไม่เกิน ${formatSize(MAX_FILE_BYTES)}`}><Paperclip /></button><span className="ss-compose-hint">Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่</span></div><button className="ss-send" onClick={() => void control.send(room.id)} disabled={!online || !!state.sending[room.id] || !draft.trim()} aria-label="ส่งข้อความ">{state.sending[room.id] ? 'กำลังส่ง…' : 'ส่ง'}<ArrowRight size={14} /></button></div>
  </div><div className="ss-composer-foot"><span className={state.notices[room.id] ? 'ss-error' : ''}>{state.notices[room.id] || (online ? 'ข้อความและไฟล์ในห้องนี้เก็บไว้ให้คุณ' : 'ขาดการเชื่อมต่อ · พิมพ์ร่างต่อได้')}</span><span className="ss-flush-status">{state.sending[room.id] ? 'กำลังส่ง…' : Object.keys(state.messages[room.id] || {}).length && !state.notices[room.id] ? 'บันทึกแล้ว' : ''}</span></div></div>
}

export default function App() {
  const state = useSyncExternalStore(control.subscribe, control.snapshot)
  const [authRequested, setAuthRequested] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [compact, setCompact] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  const closeMobile = useCallback(() => setMobile(false), [])
  const [modal, setModal] = useState<'create' | 'members' | 'directory' | 'connection' | 'search' | null>(null)
  const [tab, setTab] = useState<'chat' | 'files'>('chat')
  const [aiOpen, setAiOpen] = useState(false)
  useEffect(() => {
    void control.restoreSession()
    const changed = (event: StorageEvent) => { if (event.key === SESSION_STORAGE_KEY || event.key === null) control.storedSessionChanged() }
    window.addEventListener('storage', changed)
    return () => { window.removeEventListener('storage', changed); control.close() }
  }, [])
  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 761px)')
    const changed = () => { setCompact(!desktop.matches); if (desktop.matches) setMobile(false) }
    desktop.addEventListener('change', changed)
    return () => desktop.removeEventListener('change', changed)
  }, [])
  useEffect(() => { if (state.phase === 'authenticated') setAuthRequested(false) }, [state.phase])
  const room = state.activeRoom === null ? undefined : state.rooms[state.activeRoom]
  useEffect(() => { setTab('chat'); setAiOpen(false) }, [room?.id])
  useEffect(() => { if (state.highlight !== null) setTab('chat') }, [state.highlight])
  useEffect(() => { document.title = state.user && !authRequested ? `${room ? roomTitle(state, room) + ' — ' : ''}StudyGroup` : 'StudyGroup — เข้าสู่ระบบ' }, [state.user, room, authRequested])
  if (!state.user || authRequested) return <Auth state={state} />
  const member = room && isMember(state, room)
  const online = state.phase === 'authenticated'
  const totalUnread = Object.entries(state.unread).reduce((total, [id, count]) => Number(id) === state.activeRoom ? total : total + count, 0)
  const reconnect = () => { setModal(null); setAuthRequested(true) }
  return <div className="ss-app"><Sidebar state={state} create={() => { setMobile(false); setModal('create') }} directory={() => { setMobile(false); setModal('directory') }} connection={() => online ? setModal('connection') : reconnect()} mobile={mobile} close={closeMobile} />
    <main className="ss-main" inert={mobile}>
      <header className="ss-header"><button className="ss-icon ss-mobile-menu" onClick={() => setMobile(true)} aria-controls="room-navigation" aria-expanded={mobile} aria-label={totalUnread ? `เปิดรายชื่อห้อง มีข้อความยังไม่อ่าน ${totalUnread} ข้อความ` : 'เปิดรายชื่อห้อง'}><Menu />{totalUnread > 0 && <span className="ss-menu-unread" aria-hidden="true">{totalUnread > 99 ? '99+' : totalUnread}</span>}</button><div className="ss-heading"><span className="ss-roomicon">{room ? room.kind === 'group' ? '#' : <LockKeyhole /> : <MessageSquare />}</span><div><h1>{room ? roomTitle(state, room) : 'เริ่มบทสนทนา'}</h1><p className="ss-small">{room ? room.kind === 'group' ? `${room.members.length} สมาชิก · ${room.members.map(m => m.username).join(', ')}` : `แชตส่วนตัว · เฉพาะคุณและ ${roomTitle(state, room)}` : 'เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย'}</p></div></div><div className="ss-actions"><button className="ss-members-trigger" onClick={() => setModal('members')} disabled={!room} aria-label="ดูสมาชิก" title="ดูสมาชิก"><span className="ss-header-portraits" aria-hidden="true">{room?.members.slice(0, 3).map(member => <Avatar key={member.id} name={member.username} />)}</span><Users /></button>{room?.kind === 'group' && member && <button className="ss-btn ss-ai" aria-label="สรุปด้วย AI" aria-expanded={aiOpen} onClick={() => { if (aiOpen) setAiOpen(false); else { setAiOpen(true); setTab('chat'); if (!state.ai[room.id]?.result && !state.ai[room.id]?.loading) void control.summarize(room.id) } }} disabled={!online} title="สรุปประเด็น ข้อตกลง งาน และกำหนดส่งด้วย AI"><Sparkles /> <span className="ss-ai-label">สรุปด้วย AI</span></button>}</div></header>
      {(!room || member) && <div className="ss-tabs"><div className="ss-tabset" role="tablist" aria-label="เนื้อหาห้อง"><button className="ss-tab" role="tab" aria-selected={tab === 'chat'} onClick={() => setTab('chat')} disabled={!room}>แชต</button><button className="ss-tab" role="tab" aria-selected={tab === 'files'} onClick={() => setTab('files')} disabled={!room}>ไฟล์</button></div><button className="ss-search-trigger" onClick={() => setModal('search')} disabled={!room || !online} aria-label="ค้นหาข้อความ" title="ค้นหาด้วยคำและช่วงวันที่ในห้องนี้"><Search size={14} /><span>ค้นหาข้อความ</span></button></div>}
      {(state.error || !online) && <div className="ss-banner" role="alert"><WifiOff size={16} /><span>{state.error || 'ขาดการเชื่อมต่อ กรุณาเข้าสู่ระบบใหม่'}</span>{!online ? <button onClick={reconnect}>เข้าสู่ระบบใหม่</button> : <button onClick={() => control.clearError()} aria-label="ปิดข้อความผิดพลาด"><X size={15} /></button>}</div>}
      {!room ? <div className="ss-empty ss-welcome"><MessageSquare /><h2>พื้นที่คุยงานของทีมคุณ</h2><p>เลือกคนออนไลน์เพื่อเริ่มแชตส่วนตัว<br />หรือสร้างกลุ่มเพื่อแบ่งงานกับเพื่อน</p><button className="ss-btn ss-primary" onClick={() => setModal('create')} disabled={!online}><Plus /> สร้างกลุ่มใหม่</button></div>
        : member ? <>{aiOpen && !compact && room.kind === 'group' && tab === 'chat' && <AIPanel state={state} room={room} close={() => setAiOpen(false)} />}{tab === 'files' ? <FilesPanel state={state} room={room} /> : <Transcript state={state} room={room} />}<Composer state={state} room={room} /></>
          : <div className="ss-join-wrap"><div className="ss-empty"><Users /><p>พื้นที่คุยงานของ {room.members.map(m => m.username).join(', ')}</p></div><section className="ss-join-panel"><h2>เข้าร่วม {room.name}</h2><p className="ss-small">เข้าร่วมก่อนจึงจะอ่านและส่งข้อความในห้องนี้ได้</p><button className="ss-btn ss-primary" disabled={!online} onClick={() => void control.joinGroup(room.id)}><Plus /> เข้าร่วมด้วยตัวเอง</button></section></div>}
    </main>
    {aiOpen && compact && room?.kind === 'group' && member && tab === 'chat' && <Modal className="ss-ai-modal" title={`สรุปด้วย AI · ${room.name}`} closeLabel="ปิดสรุป AI" returnFocus={'[aria-label="สรุปด้วย AI"]'} close={() => setAiOpen(false)}><AIPanel state={state} room={room} close={() => setAiOpen(false)} /></Modal>}
    {modal === 'create' && <Modal title="สร้างกลุ่มใหม่" close={() => setModal(null)}><GroupForm close={() => setModal(null)} /></Modal>}
    {modal === 'search' && room && member && <Modal title={`ค้นหาใน ${roomTitle(state, room)}`} close={() => setModal(null)}><SearchPanel state={state} room={room} close={() => setModal(null)} /></Modal>}
    {modal === 'directory' && <Modal title="สำรวจกลุ่มทั้งหมด" close={() => setModal(null)}><Directory state={state} close={() => setModal(null)} /></Modal>}
    {modal === 'members' && room && <Modal title={`สมาชิก · ${room.members.length} คน`} close={() => setModal(null)}><div className="ss-members">{room.members.map(member => <div className="ss-member" key={member.id}><Avatar name={member.username} own={member.id === state.user!.id} /><span>{member.username}{member.id === state.user!.id && <span className="ss-small"> (คุณ)</span>}</span></div>)}</div></Modal>}
    {modal === 'connection' && <Modal title="การเชื่อมต่อ" close={() => setModal(null)}><div className="ss-connection-detail"><Wifi /><div><strong>เชื่อมต่อแล้ว</strong><p>{window.location.host}</p><p className="ss-small">{window.location.protocol === 'https:' ? 'WebSocket ผ่านการเชื่อมต่อเข้ารหัส' : 'WebSocket สำหรับการพัฒนาในเครื่อง'}</p></div><Check /></div></Modal>}
  </div>
}
