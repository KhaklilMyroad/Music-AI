import { useCallback, useEffect, useRef, useState } from 'react'
import { api, SongPlan, Track } from './api'
import { ARRANGEMENTS, COMPOSE_PLANS, GENRE_PRESETS, PRESET_FAMILIES } from './presets'
import { StudioView } from './Studio'

const LANGS = ['english', 'hebrew', 'spanish', 'french', 'japanese', 'arabic', 'german', 'portuguese']
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface Health {
  engine_reachable: boolean
  mastering_ready?: boolean
  producer_reachable?: boolean
}

type View =
  | { name: 'create' }
  | { name: 'library' }
  | { name: 'track'; id: string }
  | { name: 'studio'; id?: string }

function coverHue(id: string): number {
  let h = 0
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360
  return h
}

function coverStyle(id: string) {
  return {
    background: `linear-gradient(135deg, hsl(${coverHue(id)} 72% 46%), hsl(${(coverHue(id) + 70) % 360} 72% 28%))`,
  }
}

function fmt(s?: number | null): string {
  if (s == null || Number.isNaN(s)) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

const TYPE_LABEL: Record<string, string> = {
  text2music: 'One shot', compose: 'Composed', cover: 'Cover',
  extract: 'Stems', repaint: 'Repaint', complete: 'Extended',
}

/** AI cover art generated from the track's style prompt (free Pollinations API),
 *  with the gradient as an instant/offline fallback. Deterministic per track. */
function CoverArt({ track, className, children }: {
  track: Track
  className?: string
  children?: React.ReactNode
}) {
  const [loaded, setLoaded] = useState(false)
  const seed = coverHue(track.id) * 131 + track.id.charCodeAt(0)
  const prompt = encodeURIComponent(
    `album cover art, ${(track.prompt || track.title).slice(0, 180)}, moody professional music artwork, no text`,
  )
  const url = `https://image.pollinations.ai/prompt/${prompt}?width=512&height=512&nologo=true&seed=${seed}`
  return (
    <div className={`cover ${className ?? ''}`} style={coverStyle(track.id)}>
      <img className="cover-img" src={url} alt="" loading="lazy"
        style={{ opacity: loaded ? 1 : 0 }}
        onLoad={() => setLoaded(true)} onError={() => setLoaded(false)} />
      {children}
    </div>
  )
}

export default function App() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [view, setView] = useState<View>({ name: 'create' })
  const [playing, setPlaying] = useState<Track | null>(null)
  const [error, setError] = useState('')
  const [health, setHealth] = useState<Health | null>(null)

  const refresh = useCallback(async () => {
    try {
      setTracks(await api.listSongs())
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const pollHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`)
      setHealth(await res.json())
    } catch {
      setHealth(null)
    }
  }, [])

  useEffect(() => {
    refresh(); pollHealth()
    const iv = setInterval(refresh, 4000)
    const hv = setInterval(pollHealth, 10000)
    return () => { clearInterval(iv); clearInterval(hv) }
  }, [refresh, pollHealth])

  const current = view.name === 'track' ? tracks.find(t => t.id === view.id) ?? null : null

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand" onClick={() => setView({ name: 'create' })} style={{ cursor: 'pointer' }}>
          <span className="logo">♪</span>
          <div>
            <h1>Crescendo</h1>
            <span className="tag">AI Music Studio</span>
          </div>
        </div>
        <nav>
          <a className={`nav-item ${view.name === 'create' ? 'active' : ''}`} onClick={() => setView({ name: 'create' })}>🎛 Create</a>
          <a className={`nav-item ${view.name === 'library' || view.name === 'track' ? 'active' : ''}`} onClick={() => setView({ name: 'library' })}>
            🎵 Library <span className="count">{tracks.length}</span>
          </a>
          <a className={`nav-item ${view.name === 'studio' ? 'active' : ''}`} onClick={() => setView({ name: 'studio' })}>
            🎚 Studio
          </a>
        </nav>
        <div className="sidebar-status">
          <span className={`pill ${health?.engine_reachable ? 'on' : 'off'}`}>● Engine</span>
          <span className={`pill ${health?.mastering_ready ? 'on' : 'off'}`}>● Mastering</span>
          <span className={`pill ${health?.producer_reachable ? 'on' : 'off'}`}>● Producer</span>
        </div>
        <div className="sidebar-foot">Your GPU · your music<br />no credits, ever</div>
      </aside>

      <div className="content">
        {error && (
          <div className="toast" onClick={() => setError('')}>
            <strong>Something went wrong</strong>
            <span>{error}</span>
            <em>click to dismiss</em>
          </div>
        )}
        {view.name === 'create' && (
          <CreateView onCreated={() => { refresh(); setView({ name: 'library' }) }} onError={setError} />
        )}
        {view.name === 'library' && (
          <LibraryView tracks={tracks} playing={playing} onPlay={setPlaying}
            onOpen={id => setView({ name: 'track', id })} />
        )}
        {view.name === 'track' && current && (
          <TrackView track={current} tracks={tracks} playing={playing} onPlay={setPlaying}
            onOpen={id => setView({ name: 'track', id })}
            onBack={() => setView({ name: 'library' })}
            onChanged={refresh} onError={setError}
            onDeleted={() => { refresh(); setView({ name: 'library' }) }}
            onStudio={id => setView({ name: 'studio', id })} />
        )}
        {view.name === 'track' && !current && (
          <div className="empty"><span>🎵</span><p>Track not found.</p></div>
        )}
        {view.name === 'studio' && (
          <StudioView tracks={tracks} initialId={view.id} onError={setError}
            onChanged={refresh} onOpenTrack={id => setView({ name: 'track', id })} />
        )}
      </div>

      <PlayerBar track={playing} onEnded={() => setPlaying(null)} />
    </div>
  )
}

/* ---------------- global bottom player ---------------- */

function PlayerBar({ track, onEnded }: { track: Track | null; onEnded: () => void }) {
  const ref = useRef<HTMLAudioElement>(null)
  const [paused, setPaused] = useState(false)
  const [pos, setPos] = useState(0)
  const [len, setLen] = useState(0)

  useEffect(() => {
    if (track && ref.current) {
      ref.current.src = api.audioUrl(track.id)
      ref.current.play().catch(() => undefined)
      setPaused(false)
    }
  }, [track?.id])

  if (!track) return null
  return (
    <div className="player-bar">
      <audio
        ref={ref}
        onTimeUpdate={e => setPos(e.currentTarget.currentTime)}
        onDurationChange={e => setLen(e.currentTarget.duration)}
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        onEnded={onEnded}
      />
      <CoverArt track={track} className="small">♪</CoverArt>
      <div className="player-meta">
        <strong>{track.title}</strong>
        <small>{track.bpm ? `${track.bpm} bpm · ` : ''}{track.key_scale ?? ''}</small>
      </div>
      <button className="play-btn" onClick={() => {
        const a = ref.current
        if (!a) return
        if (a.paused) a.play().catch(() => undefined); else a.pause()
      }}>
        {paused ? '▶' : '⏸'}
      </button>
      <span className="time">{fmt(pos)}</span>
      <input
        className="seek" type="range" min={0} max={len || 1} step={0.5} value={pos}
        onChange={e => { if (ref.current) ref.current.currentTime = Number(e.target.value) }}
      />
      <span className="time">{fmt(len)}</span>
      <a className="download" href={`${api.audioUrl(track.id)}?download=1`}>⬇</a>
    </div>
  )
}

/* ---------------- create view ---------------- */

function CreateView({ onCreated, onError }: { onCreated: () => void; onError: (m: string) => void }) {
  const [idea, setIdea] = useState('')
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [language, setLanguage] = useState('english')
  const [duration, setDuration] = useState(120)
  const [takes, setTakes] = useState(1)
  const [busy, setBusy] = useState('')
  const [presetId, setPresetId] = useState('')
  const [bpm, setBpm] = useState<number | null>(null)
  const [instrumental, setInstrumental] = useState(false)
  const [quality, setQuality] = useState<'draft' | 'pro'>('pro')
  const [planner, setPlanner] = useState<'lm' | 'direct'>('lm')

  const family = GENRE_PRESETS.find(p => p.id === presetId)?.family ?? 'House'

  const insertArrangement = () => {
    setInstrumental(false)
    setLyrics(current => (current.trim() ? `${ARRANGEMENTS[family]}\n\n${current}` : ARRANGEMENTS[family]))
  }

  const applyPreset = (id: string) => {
    setPresetId(id)
    const preset = GENRE_PRESETS.find(p => p.id === id)
    if (preset) {
      setPrompt(preset.prompt)
      setBpm(preset.bpm)
    }
  }

  const applyPlan = (p: SongPlan) => {
    setTitle(p.title ?? '')
    setPrompt(p.prompt ?? '')
    setLyrics(p.lyrics ?? '')
    if (p.duration) setDuration(p.duration)
    if (p.vocal_language) setLanguage(p.vocal_language)
  }

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label)
    try {
      await fn()
    } catch (e) {
      onError(String(e))
    } finally {
      setBusy('')
    }
  }

  const qualityBody = quality === 'pro'
    ? { model: 'acestep-v15-sft', inference_steps: 50 }
    : { model: 'acestep-v15-turbo' }

  return (
    <div className="view narrow">
      <h2 className="view-title">Create</h2>

      <div className="field-group">
        <label>Your idea (any language)</label>
        <textarea value={idea} onChange={e => setIdea(e.target.value)} rows={2}
          placeholder="e.g. שיר אפרו-האוס עם הוק שחוזר / a melodic techno journey about the desert" />
        <div className="row">
          <button disabled={!idea || !!busy} onClick={() => run('plan', async () => applyPlan(await api.plan(idea, language)))}>
            {busy === 'plan' ? <span className="spin" /> : '🪄'} AI Producer: plan full song
          </button>
          <button disabled={!idea || !!busy} onClick={() => run('enhance', async () => setPrompt((await api.enhance(idea)).prompt))}>
            {busy === 'enhance' ? <span className="spin" /> : '✨'} Enhance prompt
          </button>
          <button disabled={!idea || !!busy} onClick={() => run('lyrics', async () => setLyrics((await api.lyrics(idea, language, prompt)).lyrics))}>
            {busy === 'lyrics' ? <span className="spin" /> : '📝'} Write lyrics
          </button>
        </div>
      </div>

      <div className="field-group">
        <label>Genre preset</label>
        <select value={presetId} onChange={e => applyPreset(e.target.value)}>
          <option value="">— pick a genre (fills prompt + BPM) —</option>
          {PRESET_FAMILIES.map(f => (
            <optgroup key={f} label={f}>
              {GENRE_PRESETS.filter(p => p.family === f).map(p => (
                <option key={p.id} value={p.id}>{p.label} · {p.bpm} bpm</option>
              ))}
            </optgroup>
          ))}
        </select>

        <label>Title</label>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Track title" />

        <label>Style prompt</label>
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={2}
          placeholder="genre, mood, instruments, production…" />

        <label className="check">
          <input type="checkbox" checked={instrumental}
            onChange={e => { setInstrumental(e.target.checked); if (e.target.checked) setLyrics('') }} />
          Instrumental (no vocals)
        </label>
        {!instrumental && (
          <>
            <label>Lyrics / arrangement script</label>
            <textarea value={lyrics} onChange={e => setLyrics(e.target.value)} rows={6} dir="auto"
              placeholder="[verse] … [chorus] … or use the buttons above" />
          </>
        )}
        <div className="row">
          <button disabled={!!busy} onClick={insertArrangement}>🏗 Insert club structure ({family})</button>
        </div>
      </div>

      <div className="field-group">
        <div className="row controls">
          <label>Language
            <select value={language} onChange={e => setLanguage(e.target.value)}>
              {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label>Duration · {fmt(duration)}
            <input type="range" min={30} max={300} step={10} value={duration}
              onChange={e => setDuration(Number(e.target.value))} />
          </label>
          <label>Takes
            <select value={takes} onChange={e => setTakes(Number(e.target.value))}>
              {[1, 2, 4, 8].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label>Quality
            <select value={quality} onChange={e => setQuality(e.target.value as 'draft' | 'pro')}>
              <option value="draft">Draft · fast sketch</option>
              <option value="pro">Pro · full quality</option>
            </select>
          </label>
          <label title="Engine LM: the engine's language model plans the song. Direct: the synthesizer follows your script exactly — best when the AI Producer or Compose already wrote a full blueprint">
            Planner
            <select value={planner} onChange={e => setPlanner(e.target.value as 'lm' | 'direct')}>
              <option value="lm">Engine LM</option>
              <option value="direct">Direct · my script</option>
            </select>
          </label>
        </div>
      </div>

      <button className="primary" disabled={!prompt || !!busy}
        onClick={() => run('gen', async () => {
          await api.createSong({
            title: title || undefined, prompt, lyrics: instrumental ? '' : lyrics, duration,
            vocal_language: language, batch_size: takes, bpm: bpm ?? undefined,
            thinking: planner === 'lm', ...qualityBody,
          })
          onCreated()
        })}>
        {busy === 'gen' ? 'Submitting…' : '🎧 Generate · one shot'}
      </button>

      <button className="primary compose" disabled={!prompt || !!busy}
        title="Builds the track section-by-section with a real energy arc, then masters it"
        onClick={() => run('compose', async () => {
          const plan = COMPOSE_PLANS[family]
          const hook = instrumental ? '' : lyrics
          await api.composeSong({
            title: title || undefined,
            base_prompt: bpm ? `${prompt}, ${bpm} bpm, professional club mix` : `${prompt}, professional club mix`,
            vocal_language: language,
            sections: plan.map(s => ({
              name: s.name,
              prompt: s.prompt,
              duration: Math.min(120, Math.max(5, Math.round(duration * s.weight))),
              lyrics: s.vocal ? hook : '',
              gain: s.gain,
            })),
            thinking: planner === 'lm',
            ...qualityBody,
          })
          onCreated()
        })}>
        {busy === 'compose' ? 'Composing…' : `🎼 Compose full arrangement · ${family} arc`}
      </button>
    </div>
  )
}

/* ---------------- library view ---------------- */

type SortKey = 'newest' | 'oldest' | 'title'

function LibraryView({ tracks, playing, onPlay, onOpen }: {
  tracks: Track[]
  playing: Track | null
  onPlay: (t: Track) => void
  onOpen: (id: string) => void
}) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')

  const shown = tracks
    .filter(t => !query || t.title.toLowerCase().includes(query.toLowerCase()) || t.prompt.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => {
      if (sort === 'title') return a.title.localeCompare(b.title)
      const d = a.created_at.localeCompare(b.created_at)
      return sort === 'newest' ? -d : d
    })

  return (
    <div className="view">
      <h2 className="view-title">Library</h2>
      <div className="library-tools">
        <input placeholder="🔍 Search tracks…" value={query} onChange={e => setQuery(e.target.value)} />
        <select value={sort} onChange={e => setSort(e.target.value as SortKey)}>
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="title">Title A→Z</option>
        </select>
      </div>

      {shown.length === 0 && (
        <div className="empty">
          <span>🎵</span>
          <p>{tracks.length === 0
            ? <>No tracks yet.<br />Head to Create, pick a genre, hit Compose.</>
            : 'No tracks match your search.'}</p>
        </div>
      )}

      <ul className="lib-rows">
        {shown.map(t => (
          <li key={t.id} onClick={() => onOpen(t.id)}>
            <CoverArt track={t} className="big">
              {t.status === 'generating' || t.status === 'queued'
                ? <span className="spin light" />
                : t.status === 'ready'
                  ? <button className="cover-play" onClick={e => { e.stopPropagation(); onPlay(t) }}>
                      {playing?.id === t.id ? '♫' : '▶'}
                    </button>
                  : '♪'}
              {t.duration ? <span className="dur">{fmt(t.duration)}</span> : null}
            </CoverArt>
            <div className="lib-meta">
              <div className="lib-title">
                <strong>{t.title}</strong>
                <span className="chip">{TYPE_LABEL[t.task_type] ?? t.task_type}</span>
                {t.bpm ? <span className="chip subtle">{t.bpm} bpm</span> : null}
                {t.key_scale ? <span className="chip subtle">{t.key_scale}</span> : null}
              </div>
              <p className="lib-desc">{t.prompt}</p>
              <small className="muted">
                {t.stage ?? t.status} · {fmtDate(t.created_at)}
              </small>
              {(t.status === 'generating' || t.status === 'queued') && <div className="bar"><div /></div>}
            </div>
            <span className={`dot ${t.status}`} title={t.status} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ---------------- track view ---------------- */

function TrackView({ track, tracks, playing, onPlay, onOpen, onBack, onChanged, onError, onDeleted, onStudio }: {
  track: Track
  tracks: Track[]
  playing: Track | null
  onPlay: (t: Track) => void
  onOpen: (id: string) => void
  onBack: () => void
  onChanged: () => void
  onError: (m: string) => void
  onDeleted: () => void
  onStudio?: (id: string) => void
}) {
  const [editPrompt, setEditPrompt] = useState('')
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(10)
  const [strength, setStrength] = useState(0.7)
  const [busy, setBusy] = useState(false)

  const parent = track.parent_id ? tracks.find(t => t.id === track.parent_id) : null
  const children = tracks.filter(t => t.parent_id === track.id)

  const act = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true)
    try {
      await fn()
      onChanged()
      after?.()
    } catch (e) {
      onError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="view">
      <button className="back" onClick={onBack}>← Library</button>
      <div className="track-hero">
        <CoverArt track={track} className="hero">
          {track.status === 'ready'
            ? <button className="cover-play big" onClick={() => onPlay(track)}>{playing?.id === track.id ? '♫' : '▶'}</button>
            : (track.status === 'failed' ? '✕' : <span className="spin light" />)}
        </CoverArt>
        <div className="track-info">
          <h2>{track.title}</h2>
          <div className="lib-title">
            <span className="chip">{TYPE_LABEL[track.task_type] ?? track.task_type}</span>
            {track.bpm ? <span className="chip subtle">{track.bpm} bpm</span> : null}
            {track.key_scale ? <span className="chip subtle">{track.key_scale}</span> : null}
            {track.time_signature ? <span className="chip subtle">{track.time_signature}</span> : null}
            {track.duration ? <span className="chip subtle">{fmt(track.duration)}</span> : null}
          </div>
          <p className="track-desc">{track.prompt}</p>
          <small className="muted">{fmtDate(track.created_at)}{track.vocal_language ? ` · ${track.vocal_language}` : ''}</small>
          <div className="row" style={{ marginTop: 14 }}>
            {track.status === 'ready' && (
              <>
                <button className="primary inline" onClick={() => onPlay(track)}>▶ Play</button>
                {onStudio && <button onClick={() => onStudio(track.id)}>🎚 Open in Studio</button>}
                <a className="download" href={`${api.audioUrl(track.id)}?download=1`}>⬇ Download</a>
              </>
            )}
            <button className="danger" disabled={busy}
              onClick={() => act(() => api.deleteSong(track.id), onDeleted)}>🗑 Delete</button>
          </div>
          {track.status === 'failed' && <p className="fail">{track.error}</p>}
          {(track.status === 'queued' || track.status === 'generating') && (
            <p className="muted working"><span className="spin" /> {track.stage ?? track.status}…</p>
          )}
        </div>
      </div>

      <div className="track-columns">
        <div>
          {track.status === 'ready' && (
            <div className="field-group">
              <h3>Studio</h3>
              <label>Edit prompt (repaint / cover / extend)</label>
              <input value={editPrompt} onChange={e => setEditPrompt(e.target.value)}
                placeholder="new style or direction…" />
              <div className="row">
                <button disabled={busy} onClick={() => act(() => api.stems(track.id))}>🎚 Split stems</button>
                <button disabled={busy || !editPrompt} onClick={() => act(() => api.cover(track.id, editPrompt, strength))}>🎭 Cover</button>
                <button disabled={busy || !editPrompt} onClick={() => act(() => api.extend(track.id, editPrompt))}>➕ Extend</button>
              </div>
              <div className="row">
                <label>From <input type="number" min={0} value={start} onChange={e => setStart(Number(e.target.value))} style={{ width: 70 }} />s</label>
                <label>To <input type="number" min={1} value={end} onChange={e => setEnd(Number(e.target.value))} style={{ width: 70 }} />s</label>
                <button disabled={busy || !editPrompt || end <= start}
                  onClick={() => act(() => api.repaint(track.id, editPrompt, start, end))}>
                  🖌 Repaint section
                </button>
                <label>Cover strength {strength}
                  <input type="range" min={0} max={1} step={0.05} value={strength}
                    onChange={e => setStrength(Number(e.target.value))} />
                </label>
              </div>
            </div>
          )}
          {track.lyrics && (
            <div className="field-group">
              <h3>Lyrics / arrangement</h3>
              <pre dir="auto">{track.lyrics}</pre>
            </div>
          )}
        </div>

        <div>
          <div className="field-group">
            <h3>Versions & remixes</h3>
            {!parent && children.length === 0 && (
              <p className="muted">Nothing yet — use the Studio tools to create stems, covers and extensions of this track. They'll appear here as a family tree.</p>
            )}
            {parent && (
              <div className="rel-row" onClick={() => onOpen(parent.id)}>
                <CoverArt track={parent} className="small">♪</CoverArt>
                <div><strong>{parent.title}</strong><small className="muted"> · source</small></div>
              </div>
            )}
            {children.map(c => (
              <div className="rel-row" key={c.id} onClick={() => onOpen(c.id)}>
                <CoverArt track={c} className="small">
                  {c.status === 'generating' || c.status === 'queued' ? <span className="spin light" /> : '♪'}
                </CoverArt>
                <div>
                  <strong>{c.title}</strong>
                  <small className="muted"> · {TYPE_LABEL[c.task_type] ?? c.task_type} · {c.stage ?? c.status}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
