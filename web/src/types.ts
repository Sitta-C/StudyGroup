export type User = { id: number; username: string }
export type Member = User & { joined_at: string }
export type Room = { id: number; kind: 'private' | 'group'; name: string | null; created_by: number; created_at: string; members: Member[] }
export type Attachment = { id: number; name: string; size: number; sha256: string }
export type Message = { message_id: number; room_id: number; sender_id: number; text: string | null; created_at: string; attachment?: Attachment }
export type Page = { messages: Message[]; next_before_id: number | null }
export type Summary = { topics: string[]; agreements: string[]; tasks: { task: string; owner: string; due: string }[]; deadlines: { item: string; due: string }[] }
export type AiResult = { room_id: number; summary: Summary; message_count: number; first_message_id: number | null; last_message_id: number | null; provider: string; model: string; mock: boolean; generated_at: string }
export type AiState = { loading: boolean; error: string; result: AiResult | null }
export type FileChunk = { attachment_id: number; name: string; size: number; sha256: string; offset: number; data: string; done: boolean }
export type Results = {
  REGISTER: { user: User }; LOGIN: { user: User }; LOGOUT: Record<string, never>
  USERS_LIST: { users: User[] }; PRIVATE_ROOM_OPEN: { room: Room }
  GROUP_CREATE: { room: Room }; GROUP_JOIN: { room: Room }
  GROUP_LIST: { groups: Room[]; next_after_id: number | null }
  PRIVATE_ROOM_LIST: { rooms: Room[]; next_after_id: number | null }
  MESSAGE_SEND: { message: Message }
  HISTORY_GET: Page; HISTORY_SEARCH: Page
  FILE_BEGIN: { transfer_id: string; chunk_size: number; chunks: number }
  FILE_CHUNK: { received: number }; FILE_END: { message: Message }; FILE_GET: FileChunk
  AI_SUMMARIZE: AiResult
}
export type RequestType = keyof Results
export type EventPacket = { v: number; type: string; data: Record<string, unknown>; id?: string }
export type Phase = 'disconnected' | 'connecting' | 'connected' | 'authenticated'
export type History = { loading: boolean; loaded: boolean; next: number | null; failed: boolean }
export type Transfer = { name: string; done: number; size: number; error: string }
export type State = {
  phase: Phase; authBusy: boolean; user: User | null; users: User[]
  rooms: Record<number, Room>; messages: Record<number, Record<number, Message>>
  history: Record<number, History>; ai: Record<number, AiState>; uploads: Record<number, Transfer>; downloads: Record<number, Transfer>
  drafts: Record<number, string>; unread: Record<number, number>; notices: Record<number, string>
  sending: Record<number, boolean>; activeRoom: number | null; groupsLoading: boolean
  highlight: number | null; error: string; info: string
}
