const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type TrackStatus = 'queued' | 'generating' | 'ready' | 'failed'

export interface Track {
  id: string
  title: string
  prompt: string
  lyrics: string
  task_type: string
  status: TrackStatus
  stage?: string | null
  error?: string | null
  duration?: number | null
  bpm?: number | null
  key_scale?: string | null
  time_signature?: string | null
  vocal_language?: string | null
  parent_id?: string | null
  created_at: string
}

export interface SongPlan {
  title: string
  prompt: string
  lyrics: string
  bpm?: number
  key_scale?: string
  time_signature?: string
  duration?: number
  vocal_language?: string
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${body || res.statusText}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  listSongs: () => req<Track[]>('/api/songs'),
  createSong: (body: object) =>
    req<Track>('/api/songs', { method: 'POST', body: JSON.stringify(body) }),
  composeSong: (body: object) =>
    req<Track>('/api/songs/compose', { method: 'POST', body: JSON.stringify(body) }),
  uploadSong: async (file: File, title?: string): Promise<Track> => {
    const fd = new FormData()
    fd.append('file', file)
    if (title) fd.append('title', title)
    const res = await fetch(`${BASE}/api/songs/upload`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => res.statusText)}`)
    return res.json()
  },
  deleteSong: (id: string) => req<void>(`/api/songs/${id}`, { method: 'DELETE' }),
  audioUrl: (id: string) => `${BASE}/api/songs/${id}/audio`,

  plan: (idea: string, language?: string) =>
    req<SongPlan>('/api/copilot/plan', { method: 'POST', body: JSON.stringify({ idea, language }) }),
  lyrics: (theme: string, language: string, style: string) =>
    req<{ lyrics: string }>('/api/copilot/lyrics', {
      method: 'POST',
      body: JSON.stringify({ theme, language, style }),
    }),
  enhance: (idea: string) =>
    req<{ prompt: string }>('/api/copilot/enhance', { method: 'POST', body: JSON.stringify({ idea }) }),

  repaint: (id: string, prompt: string, start: number, end: number) =>
    req<Track>(`/api/studio/${id}/repaint`, { method: 'POST', body: JSON.stringify({ prompt, start, end }) }),
  cover: (id: string, prompt: string, strength: number) =>
    req<Track>(`/api/studio/${id}/cover`, { method: 'POST', body: JSON.stringify({ prompt, strength }) }),
  stems: (id: string) => req<Track>(`/api/studio/${id}/stems`, { method: 'POST', body: '{}' }),
  extend: (id: string, prompt: string, duration?: number) =>
    req<Track>(`/api/studio/${id}/extend`, { method: 'POST', body: JSON.stringify({ prompt, duration }) }),
}
