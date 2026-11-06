export type User = { id: number; username: string }
export type Member = User & { joined_at: string }
export type Room = { id: number; kind: 'private' | 'group'; name: string | null; created_by: number; created_at: string; members: Member[] }
export type Message = { message_id: number; room_id: number; sender_id: number; text: string; created_at: string }
export type Results = {
  REGISTER: { user: User }; LOGIN: { user: User }; LOGOUT: Record<string, never>
  USERS_LIST: { users: User[] }; PRIVATE_ROOM_OPEN: { room: Room }
  GROUP_CREATE: { room: Room }; GROUP_JOIN: { room: Room }
  GROUP_LIST: { groups: Room[]; next_after_id: number | null }
  MESSAGE_SEND: { message: Message }
}
export type RequestType = keyof Results
export type EventPacket = { v: number; type: string; data: Record<string, unknown>; id?: string }
export type Phase = 'disconnected' | 'connecting' | 'connected' | 'authenticated'
export type State = {
  phase: Phase; authBusy: boolean; user: User | null; users: User[]
  rooms: Record<number, Room>; messages: Record<number, Record<number, Message>>
  drafts: Record<number, string>; unread: Record<number, number>; notices: Record<number, string>
  sending: Record<number, boolean>; activeRoom: number | null; groupsLoading: boolean
  error: string; info: string
}
