import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ArrowUp, Check, ChevronRight, Compass, Layers, LockKeyhole, LogOut, Menu, MessageSquare, Paperclip, Plus, Search, Settings2, Sparkles, Users, Wifi, WifiOff, X } from 'lucide-react'
import { ChatController, isMember, roomTitle } from './chat'
import type { Room, State } from './types'

const control = new ChatController()
function Avatar({ name, own = false, online = false }: { name: string; own?: boolean; online?: boolean }) {
  return <span className={`ss-avatar${own ? ' ss-self' : ''}`} aria-hidden="true">{name.slice(0, 2).toUpperCase()}{online && <span className="ss-online-dot" />}</span>
}
function Brand() { return <div className="ss-brand"><span className="ss-logo"><Layers /></span><div>StudyGroup<div className="ss-brand-sub">พื้นที่คุยงานของทีมคุณ</div></div></div> }

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
  return <main className="ss-auth"><section className="ss-auth-card">
    <Brand />
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
    <div className="ss-auth-note"><LockKeyhole size={13} /> ข้อมูลบัญชีของคุณจัดเก็บที่ Server</div>
  </section></main>
}

function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useRef(`dialog-${crypto.getRandomValues(new Uint32Array(1))[0]}`)
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close() }, [])
  return <dialog className="ss-modal" ref={ref} aria-labelledby={titleId.current} onCancel={event => { event.preventDefault(); close() }} onClick={event => { if (event.target === ref.current) { const bounds = ref.current.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close() } }}>
    <div className="ss-modal-head"><h2 id={titleId.current}>{title}</h2><button className="ss-icon" onClick={close} aria-label="ปิดหน้าต่าง"><X /></button></div>{children}
  </dialog>
}

function GroupForm({ close }: { close: () => void }) {
  const [name, setName] = useState('')
  return <form onSubmit={event => { event.preventDefault(); void control.createGroup(name); close() }}>
    <p className="ss-small">เริ่มจากคุณคนเดียว เพื่อนเลือกเข้าร่วมได้เอง</p>
    <label className="ss-field">ชื่อกลุ่ม<input className="ss-input" autoFocus required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
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
  const offline = privateRooms.filter(room => !state.users.some(user => user.id !== state.user!.id && room.members.some(member => member.id === user.id)))
  const groups = Object.values(state.rooms).filter(room => room.kind === 'group')
  const active = state.activeRoom === null ? undefined : state.rooms[state.activeRoom]
  return <>
    {mobile && <button className="ss-nav-scrim" onClick={close} aria-label="ปิดรายชื่อห้อง" />}
    <nav className={`ss-sidebar ${mobile ? 'is-open' : ''}`} aria-label="รายชื่อคนและห้องแชต">
      <Brand />
      <button className="ss-btn ss-primary ss-create" onClick={create} disabled={!online}><Plus /> สร้างกลุ่มใหม่</button>
      <div className="ss-sidebar-scroll">
        <section><div className="ss-section-title"><strong>ออนไลน์</strong><span>{state.users.length} คน</span></div>
          {state.users.map(user => { const own = user.id === state.user!.id, room = roomForPeer(user.id); return <button className={`ss-person${!own && active?.kind === 'private' && room?.id === active.id ? ' is-active' : ''}`} key={user.id} onClick={() => { if (own) setMenu(!menu); else { void control.openPrivate(user.id); close() } }} aria-label={own ? `บัญชี ${user.username}` : `แชตส่วนตัวกับ ${user.username}`}>
            <Avatar name={user.username} own={own} online /><span className="ss-label"><span className="ss-name">{user.username}{own && <span className="ss-small"> (คุณ)</span>}</span><span className="ss-small ss-row-detail">{own ? 'พร้อมคุยงาน' : 'ส่งข้อความส่วนตัว'}</span></span>{room && !!state.unread[room.id] && <span className="ss-unread">{state.unread[room.id]}</span>}
          </button> })}
          {!state.users.length && <p className="ss-small ss-list-empty">{online ? 'กำลังโหลดรายชื่อ…' : 'ขาดการเชื่อมต่อ'}</p>}
        </section>
        {!!offline.length && <section><div className="ss-section-title"><strong>แชตส่วนตัว</strong></div>{offline.map(room => <button className={`ss-person${room.id === state.activeRoom ? ' is-active' : ''}`} key={room.id} onClick={() => { control.selectRoom(room.id); close() }}><Avatar name={roomTitle(state, room)} /><span className="ss-label"><span className="ss-name">{roomTitle(state, room)}</span><span className="ss-small ss-row-detail">ออฟไลน์</span></span>{!!state.unread[room.id] && <span className="ss-unread">{state.unread[room.id]}</span>}</button>)}</section>}
        <section><div className="ss-section-title"><strong>ห้องกลุ่ม</strong><button className="ss-icon" onClick={create} disabled={!online} aria-label="สร้างกลุ่ม"><Plus /></button></div>
          {groups.map(room => <button className={`ss-room${state.activeRoom === room.id ? ' is-active' : ''}`} key={room.id} onClick={() => { control.selectRoom(room.id); close() }} aria-label={`เปิดห้อง ${room.name}`} title={`${room.name}\n${room.members.map(member => member.username).join(', ')}`}><span className="ss-roomicon">#</span><span className="ss-label"><span className="ss-name">{room.name}</span><span className="ss-small ss-row-detail">{room.members.map(member => member.username).join(', ')}</span></span>{!isMember(state, room) ? <span className="ss-badge">เข้าร่วม</span> : !!state.unread[room.id] && <span className="ss-unread">{state.unread[room.id]}</span>}</button>)}
          <button className="ss-link" onClick={directory}><Compass size={14} /> สำรวจกลุ่มทั้งหมด</button>
          {state.groupsLoading && <span className="ss-small ss-loading" role="status">กำลังโหลดกลุ่ม…</span>}
        </section>
      </div>
      <div className="ss-sidebar-bottom"><button className={`ss-connection${online ? '' : ' is-offline'}`} onClick={connection}><span />{online ? 'เชื่อมต่อ Server' : 'ขาดการเชื่อมต่อ'}<ChevronRight size={14} /></button>
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
function Transcript({ state, room }: { state: State; room: Room }) {
  const ref = useRef<HTMLDivElement>(null)
  const nearBottom = useRef(true)
  const previous = useRef<number | null>(null)
  const messages = Object.values(state.messages[room.id] || {}).sort((a, b) => a.message_id - b.message_id)
  const last = messages.at(-1)
  useLayoutEffect(() => {
    const changed = previous.current !== room.id
    if (ref.current && (changed || nearBottom.current || last?.sender_id === state.user!.id)) ref.current.scrollTop = ref.current.scrollHeight
    previous.current = room.id
  }, [room.id, messages.length, last?.message_id, state.user])
  let previousDate = ''
  return <div className="ss-chat-body" ref={ref} onScroll={() => { const element = ref.current!; nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 70 }} role="log" aria-label="ข้อความในห้อง" aria-live="polite" aria-relevant="additions">
    {!messages.length && <div className="ss-empty"><MessageSquare /><p>ยังไม่มีข้อความใหม่ในห้องนี้</p><span className="ss-small">ข้อความที่ได้รับระหว่างเปิดแอปจะแสดงที่นี่</span></div>}
    {messages.map(message => {
      const date = new Date(message.created_at), key = date.toDateString(), showDay = key !== previousDate
      previousDate = key
      const own = message.sender_id === state.user!.id
      const sender = room.members.find(member => member.id === message.sender_id)?.username || `ผู้ใช้ ${message.sender_id}`
      return <div className="ss-message-item" key={message.message_id}>{showDay && <div className="ss-day"><span>{dayLabel(date)}</span></div>}<article className={`ss-message ${own ? 'ss-mine' : ''}`} data-message-id={message.message_id}>
        {!own && <Avatar name={sender} />}
        <div className="ss-message-body"><div className="ss-message-meta"><span>{own ? 'คุณ' : sender}</span><time dateTime={message.created_at}>{new Intl.DateTimeFormat('th-TH', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date)}</time></div><p className="ss-bubble">{message.text}</p></div>
      </article></div>
    })}
  </div>
}

function Composer({ state, room }: { state: State; room: Room }) {
  const draft = state.drafts[room.id] || ''
  const textarea = useRef<HTMLTextAreaElement>(null)
  const [composing, setComposing] = useState(false)
  useEffect(() => { textarea.current?.focus() }, [room.id])
  return <div className="ss-compose-wrap"><div className="ss-compose">
    <textarea ref={textarea} rows={1} aria-label="ข้อความแชต" placeholder={room.kind === 'group' ? 'พิมพ์ข้อความถึงทีม…' : `พิมพ์ข้อความถึง ${roomTitle(state, room)}…`} value={draft} onChange={event => control.setDraft(room.id, event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={() => setComposing(false)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !composing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); void control.send(room.id) } }} />
    <div className="ss-compose-toolbar"><div className="ss-compose-tools"><button className="ss-icon" disabled aria-label="แนบไฟล์ (ยังไม่เปิดใช้งาน)" title="การแนบไฟล์ยังไม่เปิดใช้งาน"><Paperclip /></button><span className="ss-compose-hint">Enter เพื่อส่ง · Shift + Enter ขึ้นบรรทัดใหม่</span></div><button className="ss-send" onClick={() => void control.send(room.id)} disabled={state.phase !== 'authenticated' || !!state.sending[room.id] || !draft.trim()} aria-label="ส่งข้อความ">{state.sending[room.id] ? 'กำลังส่ง…' : 'ส่ง'}<ArrowUp size={14} /></button></div>
  </div><div className="ss-composer-foot"><span className={state.notices[room.id] ? 'ss-error' : ''}>{state.notices[room.id] || (state.phase === 'authenticated' ? 'ข้อความที่รับระหว่างเปิดแอปครั้งนี้' : 'ขาดการเชื่อมต่อ · พิมพ์ร่างต่อได้')}</span><span className="ss-flush-status">{state.sending[room.id] ? 'กำลังส่ง…' : Object.keys(state.messages[room.id] || {}).length && !state.notices[room.id] ? 'บันทึกแล้ว' : ''}</span></div></div>
}

export default function App() {
  const state = useSyncExternalStore(control.subscribe, control.snapshot)
  const [authRequested, setAuthRequested] = useState(false)
  const [mobile, setMobile] = useState(false)
  const [modal, setModal] = useState<'create' | 'members' | 'directory' | 'connection' | null>(null)
  useEffect(() => () => control.close(), [])
  useEffect(() => { if (state.phase === 'authenticated') setAuthRequested(false) }, [state.phase])
  const room = state.activeRoom === null ? undefined : state.rooms[state.activeRoom]
  useEffect(() => { document.title = state.user && !authRequested ? `${room ? roomTitle(state, room) + ' — ' : ''}StudyGroup` : 'StudyGroup — เข้าสู่ระบบ' }, [state.user, room, authRequested])
  if (!state.user || authRequested) return <Auth state={state} />
  const member = room && isMember(state, room)
  const online = state.phase === 'authenticated'
  const reconnect = () => { setModal(null); setAuthRequested(true) }
  return <div className="ss-app"><Sidebar state={state} create={() => { setMobile(false); setModal('create') }} directory={() => { setMobile(false); setModal('directory') }} connection={() => online ? setModal('connection') : reconnect()} mobile={mobile} close={() => setMobile(false)} />
    <main className="ss-main">
      <header className="ss-header"><button className="ss-icon ss-mobile-menu" onClick={() => setMobile(true)} aria-label="เปิดรายชื่อห้อง"><Menu /></button><div className="ss-heading"><span className="ss-roomicon">{room ? room.kind === 'group' ? '#' : <LockKeyhole /> : <MessageSquare />}</span><div><h1>{room ? roomTitle(state, room) : 'เริ่มบทสนทนา'}</h1><p className="ss-small">{room ? room.kind === 'group' ? `${room.members.length} สมาชิก · ${room.members.map(m => m.username).join(', ')}` : `แชตส่วนตัว · เฉพาะคุณและ ${roomTitle(state, room)}` : 'เลือกเพื่อนหรือห้องกลุ่มจากด้านซ้าย'}</p></div></div><div className="ss-actions"><button className="ss-icon" onClick={() => setModal('members')} disabled={!room} aria-label="ดูสมาชิก"><Users /></button>{room?.kind === 'group' && member && <button className="ss-btn ss-ai" disabled title="AI สรุปบทสนทนายังไม่เปิดใช้งาน"><Sparkles /> สรุปด้วย AI</button>}</div></header>
      {(!room || member) && <div className="ss-tabs"><div className="ss-tabset" role="tablist" aria-label="เนื้อหาห้อง"><button className="ss-tab" role="tab" aria-selected="true">แชต</button><button className="ss-tab" role="tab" aria-selected="false" disabled title="การส่งไฟล์ยังไม่เปิดใช้งาน">ไฟล์</button></div><button className="ss-search-trigger" disabled title="การค้นหาประวัติยังไม่เปิดใช้งาน"><Search size={14} /><span>ค้นหาข้อความ</span></button></div>}
      {(state.error || !online) && <div className="ss-banner" role="alert"><WifiOff size={16} /><span>{state.error || 'ขาดการเชื่อมต่อ กรุณาเข้าสู่ระบบใหม่'}</span>{!online ? <button onClick={reconnect}>เข้าสู่ระบบใหม่</button> : <button onClick={() => control.clearError()} aria-label="ปิดข้อความผิดพลาด"><X size={15} /></button>}</div>}
      {!room ? <div className="ss-empty ss-welcome"><MessageSquare /><h2>พื้นที่คุยงานของทีมคุณ</h2><p>เลือกคนออนไลน์เพื่อเริ่มแชตส่วนตัว<br />หรือสร้างกลุ่มเพื่อแบ่งงานกับเพื่อน</p><button className="ss-btn ss-primary" onClick={() => setModal('create')} disabled={!online}><Plus /> สร้างกลุ่มใหม่</button></div>
        : member ? <><Transcript state={state} room={room} /><Composer state={state} room={room} /></>
          : <div className="ss-join-wrap"><div className="ss-empty"><Users /><p>พื้นที่คุยงานของ {room.members.map(m => m.username).join(', ')}</p></div><section className="ss-join-panel"><h2>เข้าร่วม {room.name}</h2><p className="ss-small">เข้าร่วมก่อนจึงจะอ่านและส่งข้อความในห้องนี้ได้</p><button className="ss-btn ss-primary" disabled={!online} onClick={() => void control.joinGroup(room.id)}><Plus /> เข้าร่วมด้วยตัวเอง</button></section></div>}
    </main>
    {modal === 'create' && <Modal title="สร้างกลุ่มใหม่" close={() => setModal(null)}><GroupForm close={() => setModal(null)} /></Modal>}
    {modal === 'directory' && <Modal title="สำรวจกลุ่มทั้งหมด" close={() => setModal(null)}><Directory state={state} close={() => setModal(null)} /></Modal>}
    {modal === 'members' && room && <Modal title={`สมาชิก · ${room.members.length} คน`} close={() => setModal(null)}><div className="ss-members">{room.members.map(member => <div className="ss-member" key={member.id}><Avatar name={member.username} own={member.id === state.user!.id} /><span>{member.username}{member.id === state.user!.id && <span className="ss-small"> (คุณ)</span>}</span></div>)}</div></Modal>}
    {modal === 'connection' && <Modal title="การเชื่อมต่อ" close={() => setModal(null)}><div className="ss-connection-detail"><Wifi /><div><strong>เชื่อมต่อแล้ว</strong><p>{window.location.host}</p><p className="ss-small">{window.location.protocol === 'https:' ? 'WebSocket ผ่านการเชื่อมต่อเข้ารหัส' : 'WebSocket สำหรับการพัฒนาในเครื่อง'}</p></div><Check /></div></Modal>}
  </div>
}
