// Electronic genre preset library: pick a genre, get a production-grade
// style prompt and the genre's canonical BPM. Lyrics stay empty = instrumental.

export interface GenrePreset {
  id: string
  label: string
  family: string
  bpm: number
  prompt: string
}

export const GENRE_PRESETS: GenrePreset[] = [
  // --- House ---
  { id: 'deep-house', label: 'Deep House', family: 'House', bpm: 122,
    prompt: 'deep house, 122 bpm, warm analog chords, deep rolling sub bass, soft shuffled hats, dusty Rhodes stabs, late night intimate club mood, smooth groove' },
  { id: 'tech-house', label: 'Tech House', family: 'House', bpm: 126,
    prompt: 'tech house, 126 bpm, punchy kick, groovy bassline, tight percussion loops, minimal vocal chops, rolling groove, club-ready mix, Hot Creations style' },
  { id: 'afro-house', label: 'Afro House', family: 'House', bpm: 122,
    prompt: 'afro house, 122 bpm, log drum bassline, tribal percussion, organic shakers, hypnotic ethnic flute lead, spiritual atmosphere, desert sunset terrace vibe' },
  { id: 'progressive-house', label: 'Progressive House', family: 'House', bpm: 126,
    prompt: 'progressive house, 126 bpm, long evolving builds, lush layered synth pads, emotional melodic breakdown, driving bassline, festival main stage energy' },
  { id: 'future-house', label: 'Future House', family: 'House', bpm: 126,
    prompt: 'future house, 126 bpm, metallic bass hook, bouncy groove, filtered buildups, crisp claps, energetic drops, Don Diablo style' },
  { id: 'slap-house', label: 'Slap House / Brazilian Bass', family: 'House', bpm: 124,
    prompt: 'slap house, brazilian bass, 124 bpm, deep punchy slapping bassline, dark minimal verses, catchy lead hook, modern car-audio energy' },
  { id: 'organic-house', label: 'Organic House / Downtempo', family: 'House', bpm: 110,
    prompt: 'organic house downtempo, 110 bpm, earthy percussion, handpan melodies, warm sub bass, nature textures, sunrise festival journey, All Day I Dream style' },

  // --- Techno ---
  { id: 'melodic-techno', label: 'Melodic Techno', family: 'Techno', bpm: 124,
    prompt: 'melodic techno, 124 bpm, dark hypnotic arpeggios, analog modular synths, deep rolling bassline, sidechained atmospheric pads, emotional breakdown, Afterlife peak time energy' },
  { id: 'peak-techno', label: 'Peak Time Techno', family: 'Techno', bpm: 132,
    prompt: 'peak time techno, 132 bpm, pounding industrial kick, driving rumble bassline, dark warehouse atmosphere, hypnotic stabs, relentless energy' },
  { id: 'minimal-techno', label: 'Minimal Techno', family: 'Techno', bpm: 128,
    prompt: 'minimal techno, 128 bpm, stripped-back groove, micro percussion details, subtle modulating synth textures, deep hypnotic repetition, Berlin after-hours mood' },
  { id: 'acid-techno', label: 'Acid Techno', family: 'Techno', bpm: 130,
    prompt: 'acid techno, 130 bpm, squelchy TB-303 acid lines, punchy analog drum machine, rising filter sweeps, raw underground rave energy' },
  { id: 'hard-techno', label: 'Hard Techno', family: 'Techno', bpm: 145,
    prompt: 'hard techno, 145 bpm, distorted pounding kick, aggressive rumble bass, industrial textures, dark rave sirens, relentless festival hard-dance energy' },

  // --- Trance ---
  { id: 'uplifting-trance', label: 'Uplifting Trance', family: 'Trance', bpm: 138,
    prompt: 'uplifting trance, 138 bpm, euphoric supersaw leads, emotional piano breakdown, rolling bassline, huge risers, hands-in-the-air anthem energy' },
  { id: 'progressive-trance', label: 'Progressive Trance', family: 'Trance', bpm: 132,
    prompt: 'progressive trance, 132 bpm, deep pulsing bassline, dreamy evolving pads, plucked melodic sequences, atmospheric breakdown, Anjunabeats style' },
  { id: 'psytrance', label: 'Psytrance', family: 'Trance', bpm: 142,
    prompt: 'psytrance, 142 bpm, rolling triplet bassline, squelchy psychedelic leads, alien FX sweeps, tribal energy, full-on night festival power' },
  { id: 'goa-trance', label: 'Goa Trance', family: 'Trance', bpm: 140,
    prompt: 'goa trance, 140 bpm, swirling eastern melodies, layered analog acid lines, hypnotic 16th-note bassline, mystical spiritual atmosphere, 90s Goa beach party' },

  // --- Bass Music ---
  { id: 'dubstep', label: 'Dubstep', family: 'Bass', bpm: 140,
    prompt: 'dubstep, 140 bpm, heavy wobble bass, aggressive growls, half-time drums, cinematic buildup, massive drop, festival bass energy' },
  { id: 'riddim', label: 'Riddim', family: 'Bass', bpm: 140,
    prompt: 'riddim dubstep, 140 bpm, repetitive wonky bass stabs, minimal dark atmosphere, bouncing triplet rhythm, mosh pit energy' },
  { id: 'dnb', label: 'Drum & Bass', family: 'Bass', bpm: 174,
    prompt: 'drum and bass, 174 bpm, fast breakbeats, deep reese bassline, dark rolling energy, crisp snares, underground rave atmosphere' },
  { id: 'liquid-dnb', label: 'Liquid DnB', family: 'Bass', bpm: 174,
    prompt: 'liquid drum and bass, 174 bpm, lush atmospheric pads, soulful chords, deep warm sub bass, crisp breakbeats, late night rain mood, emotional and smooth' },
  { id: 'jungle', label: 'Jungle', family: 'Bass', bpm: 170,
    prompt: 'jungle, 170 bpm, chopped amen breaks, deep dub bassline, ragga vocal chops as texture, 90s London pirate radio energy, gritty and raw' },
  { id: 'uk-garage', label: 'UK Garage / 2-Step', family: 'Bass', bpm: 132,
    prompt: 'UK garage 2-step, 132 bpm, shuffling swung drums, warm organ bass, chopped vocal snippets as instrument, night bus London mood, groovy and slick' },
  { id: 'future-bass', label: 'Future Bass', family: 'Bass', bpm: 150,
    prompt: 'future bass, 150 bpm, huge detuned supersaw chords, pitch-bent lead melodies, trap-influenced drums, bright euphoric drops, colorful and emotional' },
  { id: 'trap-edm', label: 'Trap (EDM)', family: 'Bass', bpm: 150,
    prompt: 'EDM trap, 150 bpm, booming 808 bass, rapid hi-hat rolls, big brass stabs, hard hitting drop, festival hype energy' },
  { id: 'phonk', label: 'Phonk', family: 'Bass', bpm: 130,
    prompt: 'drift phonk, 130 bpm, distorted cowbell melody, memphis-style dark atmosphere, punchy 808 bass, aggressive night drive energy' },

  // --- Synth / Retro / Electro ---
  { id: 'synthwave', label: 'Synthwave / Retrowave', family: 'Synth', bpm: 105,
    prompt: 'synthwave retrowave, 105 bpm, 80s analog synth arpeggios, gated reverb drums, neon nostalgic atmosphere, night drive on an empty highway, cinematic outrun mood' },
  { id: 'electro', label: 'Electro', family: 'Synth', bpm: 128,
    prompt: 'electro, 128 bpm, robotic bass stabs, vocoder textures, punchy drum machine, French electro grit, Justice style distorted energy' },
  { id: 'big-room', label: 'Big Room / Festival EDM', family: 'Synth', bpm: 128,
    prompt: 'big room EDM, 128 bpm, massive festival drop, anthemic lead melody, huge kick, crowd-pleasing buildup with snare roll, main stage fireworks energy' },
  { id: 'hardstyle', label: 'Hardstyle', family: 'Synth', bpm: 150,
    prompt: 'hardstyle, 150 bpm, distorted reverse bass kick, euphoric melodic breakdown, screeching leads, festival hard dance energy' },
  { id: 'eurodance', label: 'Eurodance / 90s', family: 'Synth', bpm: 140,
    prompt: 'eurodance, 140 bpm, 90s rave piano stabs, catchy synth hook, four-on-the-floor energy, retro club nostalgia' },
  { id: 'idm', label: 'IDM / Glitch', family: 'Synth', bpm: 120,
    prompt: 'IDM glitch electronica, 120 bpm, intricate glitchy drum programming, warm melodic synth textures, granular effects, Aphex Twin inspired, cerebral and beautiful' },
  { id: 'breakbeat', label: 'Breakbeat / Big Beat', family: 'Synth', bpm: 130,
    prompt: 'big beat breakbeat, 130 bpm, funky chopped breaks, gritty acid bass, rock-influenced energy, Chemical Brothers style, festival groove' },

  // --- Chill ---
  { id: 'ambient', label: 'Ambient', family: 'Chill', bpm: 70,
    prompt: 'ambient electronic, 70 bpm, vast evolving pad textures, gentle granular shimmer, deep slow sub swells, weightless meditative space, no drums' },
  { id: 'chillout', label: 'Chillout / Balearic', family: 'Chill', bpm: 100,
    prompt: 'balearic chillout, 100 bpm, warm dreamy guitars over soft electronic beats, sunset beach bar atmosphere, mellow groove, Café del Mar mood' },
  { id: 'lofi', label: 'Lo-fi Beats', family: 'Chill', bpm: 85,
    prompt: 'lofi hip hop beats, 85 bpm, dusty vinyl crackle, mellow jazzy piano chords, soft boom bap drums, warm tape saturation, cozy study session mood' },
  { id: 'psychill', label: 'Psychill / Psybient', family: 'Chill', bpm: 95,
    prompt: 'psychill psybient, 95 bpm, deep dubby bassline, psychedelic swirling textures, organic ethnic instruments, cosmic downtempo journey' },
  { id: 'trip-hop', label: 'Trip Hop', family: 'Chill', bpm: 90,
    prompt: 'trip hop, 90 bpm, dark cinematic strings, dusty slow breakbeats, deep moody bass, noir late-night atmosphere, Massive Attack style' },
]

export const PRESET_FAMILIES = [...new Set(GENRE_PRESETS.map(p => p.family))]

// Section Composer plans: the track is built section-by-section (each section
// continues the previous audio with its own energy prompt), so the arc is
// explicit instead of hoped-for. weight = share of the total duration.
export interface ComposeSectionPlan {
  name: string
  weight: number
  prompt: string
  vocal?: boolean // hook/vocal sections get the user's lyrics
}

export const COMPOSE_PLANS: Record<string, ComposeSectionPlan[]> = {
  House: [
    { name: 'Intro', weight: 0.1, prompt: 'stripped intro, dry drums and shaker only, filtered pads, low energy, no lead' },
    { name: 'Groove', weight: 0.12, prompt: 'bassline enters, percussion locks in, subtle melodic hints, mid energy' },
    { name: 'Build', weight: 0.08, prompt: 'rising tension, layers stacking, filter sweep up, snare roll, riser' },
    { name: 'Drop', weight: 0.2, prompt: 'full drop, main hook front and center, maximum energy, everything moving', vocal: true },
    { name: 'Breakdown', weight: 0.12, prompt: 'drums drop out, atmospheric pads and one melodic element in reverb, emotional pause' },
    { name: 'Build 2', weight: 0.08, prompt: 'percussion returning piece by piece, longest riser, biggest tension' },
    { name: 'Drop 2', weight: 0.2, prompt: 'peak moment, extra percussion layer, ad-lib textures, euphoric maximum energy', vocal: true },
    { name: 'Outro', weight: 0.1, prompt: 'elements exiting one by one, back to dry drums, filter closing, fade' },
  ],
  Techno: [
    { name: 'Intro', weight: 0.12, prompt: 'kick and rumble bass alone, dark warehouse atmosphere, hypnotic, minimal' },
    { name: 'Groove', weight: 0.13, prompt: 'hypnotic stab pattern enters, driving hats, relentless momentum' },
    { name: 'Build', weight: 0.08, prompt: 'acid line rising, white noise sweep, tension stacking' },
    { name: 'Peak', weight: 0.2, prompt: 'full power, lead synth hook cutting through, maximum drive', vocal: true },
    { name: 'Breakdown', weight: 0.12, prompt: 'kick disappears, vast dark pad, echoing lead, suspense' },
    { name: 'Build 2', weight: 0.08, prompt: 'kick returns with long riser, doubled snares, extreme tension' },
    { name: 'Peak 2', weight: 0.17, prompt: 'hardest section, all layers together, relentless drive', vocal: true },
    { name: 'Outro', weight: 0.1, prompt: 'layers stripping away, kick and rumble fading into darkness' },
  ],
  Trance: [
    { name: 'Intro', weight: 0.1, prompt: 'rolling bassline and crisp percussion, arps hinting the melody' },
    { name: 'Groove', weight: 0.12, prompt: 'plucked sequence enters, energy building steadily' },
    { name: 'Build', weight: 0.08, prompt: 'layers rising, accelerating snare roll, huge riser' },
    { name: 'Drop', weight: 0.2, prompt: 'euphoric main melody full power, wide supersaws, anthem energy', vocal: true },
    { name: 'Breakdown', weight: 0.14, prompt: 'beat stops, emotional piano and pads carry the melody alone' },
    { name: 'Build 2', weight: 0.08, prompt: 'melody rejoined by rising drums, longest riser' },
    { name: 'Drop 2', weight: 0.18, prompt: 'biggest euphoric peak, full stack, hands in the air', vocal: true },
    { name: 'Outro', weight: 0.1, prompt: 'melody fading, bassline and percussion closing' },
  ],
  Bass: [
    { name: 'Intro', weight: 0.12, prompt: 'atmospheric textures, sparse drums, dark tension' },
    { name: 'Build', weight: 0.1, prompt: 'accelerating drums, screaming riser, vocal chop echoes, snare roll' },
    { name: 'Drop', weight: 0.22, prompt: 'massive bass hook, heavy and aggressive, maximum impact', vocal: true },
    { name: 'Switch', weight: 0.12, prompt: 'bass pattern flips to new variation, fresh energy' },
    { name: 'Breakdown', weight: 0.12, prompt: 'half-time moment, airy pads, tension reset' },
    { name: 'Build 2', weight: 0.08, prompt: 'faster risers, stacking drum fills' },
    { name: 'Drop 2', weight: 0.16, prompt: 'hardest drop, extra bass layers and fills, relentless', vocal: true },
    { name: 'Outro', weight: 0.08, prompt: 'energy decaying, textures dissolving' },
  ],
  Synth: [
    { name: 'Intro', weight: 0.1, prompt: 'iconic synth riff alone with soft drum machine' },
    { name: 'Verse', weight: 0.15, prompt: 'groove settles, pumping bassline, riff developing', vocal: true },
    { name: 'Build', weight: 0.08, prompt: 'drums intensifying, climbing arpeggios, filter opening' },
    { name: 'Chorus', weight: 0.2, prompt: 'full anthem energy, soaring lead melody, wide and bright', vocal: true },
    { name: 'Breakdown', weight: 0.12, prompt: 'stripped to bass and pad, cinematic pause' },
    { name: 'Build 2', weight: 0.08, prompt: 'rolling toms, riser, energy returning' },
    { name: 'Chorus 2', weight: 0.17, prompt: 'biggest version, extra harmony layer on the lead', vocal: true },
    { name: 'Outro', weight: 0.1, prompt: 'riff alone, slow fade with reverb tails' },
  ],
  Chill: [
    { name: 'Intro', weight: 0.14, prompt: 'soft textures fading in, gentle rhythm emerging' },
    { name: 'Theme A', weight: 0.18, prompt: 'main melodic motif, warm and intimate, slow groove', vocal: true },
    { name: 'Development', weight: 0.18, prompt: 'new layer every phrase, subtle harmonic shifts, warmth rising' },
    { name: 'Peak', weight: 0.18, prompt: 'fullest moment, all layers breathing together, emotional but restrained', vocal: true },
    { name: 'Theme B', weight: 0.16, prompt: 'variation of the motif, different color, fresh perspective' },
    { name: 'Outro', weight: 0.16, prompt: 'layers thinning, last melodic echo dissolving into ambience' },
  ],
}

// Club arrangement blueprints: an energy-curve scaffold the engine follows.
// Section tags carry production directives; vocal lines can be written inside
// any section (or left as-is for instrumental).
export const ARRANGEMENTS: Record<string, string> = {
  House: `[Intro: dry drum groove and shaker only, filtered pad slowly opening, 8 bars, low energy]

[Groove: bassline enters, main percussion locks in, subtle melodic hint, head-nodding energy]

[Build: layers stack one by one, rising filter sweep, snare roll in the last bar, tension climbing]

[Drop: full groove hits hard, main hook front and center, maximum energy, everything moving]

[Breakdown: drums drop out, only atmospheric pads and one melodic element floating in reverb, emotional pause]

[Build 2: percussion returns piece by piece, longer riser, biggest tension of the track]

[Drop 2: peak moment, extra percussion layer and ad-lib textures answering the hook, euphoric]

[Outro: elements exit one by one, back to dry drums, long filter close, fade]`,

  Techno: `[Intro: pounding kick and rumble bass alone, dark warehouse atmosphere, hypnotic, 16 bars]

[Groove: hypnotic stab pattern enters, hats driving, relentless momentum]

[Build: acid line rising, white-noise sweep, tension stacking bar by bar]

[Peak: full power, lead synth hook cutting through, strobe-light energy, maximum drive]

[Breakdown: kick disappears, vast dark pad and echoing lead, suspense hanging in the air]

[Build 2: kick returns with a long riser, snares doubling, unbearable tension]

[Peak 2: hardest moment of the track, all layers together, driving to the end]

[Outro: layers strip away, kick and rumble fade into darkness]`,

  Trance: `[Intro: rolling bassline and crisp percussion, arps hinting the melody, 16 bars]

[Groove: plucked sequence enters, energy building steadily]

[Build: layers rise, snare roll accelerating, huge white-noise riser]

[Drop: euphoric main melody at full power, supersaws wide, hands-in-the-air moment]

[Breakdown: beat stops, emotional piano and pad carry the melody alone, goosebumps section]

[Build 2: melody rejoined by rising drums, longest riser of the track]

[Drop 2: biggest euphoric peak, full stack, anthem energy]

[Outro: melody fades, bassline and percussion close the journey]`,

  Bass: `[Intro: atmospheric textures and sparse drums, dark tension, 8 bars]

[Build: drums accelerate, riser screaming upward, vocal chop echoes, snare roll]

[Drop: massive bass hook hits, heavy and aggressive, maximum impact]

[Switch: bass pattern flips to a new variation, keeps the energy fresh]

[Breakdown: half-time moment, airy pads, tension resets]

[Build 2: faster risers, drum fills stacking]

[Drop 2: hardest drop, extra bass layers and fills, relentless]

[Outro: energy decays, textures dissolve into silence]`,

  Synth: `[Intro: iconic synth riff alone with soft drum machine, nostalgic mood, 8 bars]

[Verse: groove settles, bassline pumping, riff developing]

[Build: drums intensify, arpeggios climbing, filter opening]

[Chorus: full anthem energy, lead melody soaring, wide and bright]

[Breakdown: stripped to bass and pad, cinematic pause]

[Build 2: toms rolling, riser, energy returning]

[Chorus 2: biggest version, extra harmony layer on the lead]

[Outro: riff returns alone, slow fade with reverb tails]`,

  Chill: `[Intro: soft textures fade in, gentle rhythm emerging, calm]

[Theme A: main melodic motif enters, warm and intimate, slow head-nod groove]

[Development: new layer joins each 8 bars, subtle harmonic shifts, gently rising warmth]

[Peak: fullest moment, all layers breathing together, emotional but restrained]

[Theme B: variation of the motif, slightly different color, fresh perspective]

[Resolution: layers thin out gradually, returning to the opening texture]

[Outro: last melodic echo dissolves, ambience fades to silence]`,
}
