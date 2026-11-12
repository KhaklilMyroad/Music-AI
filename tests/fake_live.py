"""A small in-memory stand-in for Ableton's Live Object Model, for testing the bridge logic.

It models only what the handlers use. It is NOT evidence that the real Live API behaves the same;
API names follow the LOM documentation and Ableton's own Remote Scripts (see docs/LIVE-API.md)."""
import math


class Param:
    def __init__(self, name, value=0.0, lo=0.0, hi=1.0, display=None, quantized=False, items=None):
        self.name, self.value, self.min, self.max = name, value, lo, hi
        self._display = display or (lambda v: "%.2f" % v)
        self.is_quantized = quantized
        self.value_items = items or []

    def str_for_value(self, v):
        return self._display(v)


def volume_display(v):
    # monotonic, non-linear, like Live's fader: 0.85 -> 0 dB, 1.0 -> +6 dB, 0 -> -inf
    if v <= 0:
        return "-inf dB"
    db = 40 * math.log10(v / 0.85) if v < 0.85 else (v - 0.85) / 0.15 * 6
    return "%.1f dB" % db


def freq_display(v):  # 0..1 -> 10 Hz .. 22 kHz log
    f = 10 * (2200 ** v)
    return "%.2f kHz" % (f / 1000) if f >= 1000 else "%.1f Hz" % f


class Mixer:
    def __init__(self, n_sends):
        self.volume = Param("Track Volume", 0.85, 0, 1, volume_display)
        self.panning = Param("Track Panning", 0, -1, 1)
        self.sends = [Param("Send %s" % chr(65 + i), 0, 0, 1, volume_display) for i in range(n_sends)]


class Device:
    def __init__(self, name, class_name, params):
        self.name, self.class_name = name, class_name
        self.parameters = [Param("Device On", 1, 0, 1, quantized=True)] + params
        self.is_active = True
        self.can_have_chains = False


def make_eq():
    return Device("EQ Eight", "Eq8", [Param("1 Frequency A", 0.3, 0, 1, freq_display),
                                      Param("1 Gain A", 0, -15, 15, lambda v: "%.1f dB" % v),
                                      Param("1 Filter Type A", 3, 0, 7, lambda v: str(int(v)), True,
                                            ["LowCut48", "LowCut12", "LowShelf", "Bell", "Notch", "HighShelf", "HighCut12", "HighCut48"])])


class CompressorDevice(Device):
    def __init__(self):
        Device.__init__(self, "Compressor", "Compressor2", [Param("Threshold", 1, 0, 1), Param("S/C On", 0, 0, 1, quantized=True)])
        self.available_input_routing_types = [Routing("No Input"), Routing("1-Kick"), Routing("2-Audio")]
        self.input_routing_type = self.available_input_routing_types[0]
        self.available_input_routing_channels = [Routing("Post FX"), Routing("Pre FX")]
        self.input_routing_channel = self.available_input_routing_channels[0]


def make_comp():
    return CompressorDevice()


class Note:
    def __init__(self, pitch, start_time, duration, velocity, mute=False, note_id=0):
        self.pitch, self.start_time, self.duration, self.velocity, self.mute, self.note_id = pitch, start_time, duration, velocity, mute, note_id


class Clip:
    def __init__(self, length, midi=True, file_path=None):
        self.name, self.length = "", length
        self.is_midi_clip, self.is_audio_clip = midi, not midi
        self.looping, self.loop_start, self.loop_end = True, 0.0, length
        self.notes = []
        self.file_path = file_path
        self._ids = 0

    def get_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        return [n for n in self.notes if from_pitch <= n.pitch < from_pitch + pitch_span and from_time <= n.start_time < from_time + time_span]

    def add_new_notes(self, specs):
        for p, s, d, v, m in specs:
            self._ids += 1
            self.notes.append(Note(p, s, d, v, m, self._ids))

    def remove_notes_extended(self, from_pitch, pitch_span, from_time, time_span):
        self.notes = [n for n in self.notes if not (from_pitch <= n.pitch < from_pitch + pitch_span and from_time <= n.start_time < from_time + time_span)]

    def quantize(self, grid, amount):
        q = {"rec_q_sixtenth": 0.25, "rec_q_eight": 0.5, "rec_q_quarter": 1.0, "rec_q_thirtysecond": 0.125}[grid]
        for n in self.notes:
            n.start_time += (round(n.start_time / q) * q - n.start_time) * amount


class ClipSlot:
    def __init__(self):
        self.clip = None
        self.fired = 0

    @property
    def has_clip(self):
        return self.clip is not None

    def create_clip(self, length):
        self.clip = Clip(length)

    def create_audio_clip(self, path):
        self.clip = Clip(8.0, midi=False, file_path=path)

    def delete_clip(self):
        self.clip = None

    def fire(self):
        self.fired += 1

    def stop(self):
        pass

    def duplicate_clip_to(self, other):
        import copy
        other.clip = copy.deepcopy(self.clip)


class Routing:
    def __init__(self, name):
        self.display_name = name


class Track:
    def __init__(self, name, midi, n_scenes, n_sends):
        self.name, self.mute, self.solo, self.arm = name, False, False, False
        self.can_be_armed = True
        self.has_midi_input, self.has_audio_input = midi, not midi
        self.mixer_device = Mixer(n_sends)
        self.devices = []
        self.clip_slots = [ClipSlot() for _ in range(n_scenes)]
        self.arrangement_clips = []
        self.color_index = 0
        self.available_input_routing_types = [Routing("Ext. In"), Routing("Resampling"), Routing("No Input")]
        self.input_routing_type = self.available_input_routing_types[0]
        self.available_input_routing_channels = [Routing("1/2"), Routing("1"), Routing("2")]
        self.input_routing_channel = self.available_input_routing_channels[0]
        self.available_output_routing_types = [Routing("Main"), Routing("Sends Only")]
        self.output_routing_type = self.available_output_routing_types[0]
        self.available_output_routing_channels = [Routing("")]
        self.output_routing_channel = self.available_output_routing_channels[0]
        self.current_monitoring_state = 1
        self.output_meter_left = self.output_meter_right = 0.0

    def delete_device(self, i):
        del self.devices[i]

    def insert_device(self, name, index=None):
        known = {"EQ Eight": make_eq, "Compressor": make_comp}
        if name not in known:
            raise RuntimeError("unknown device")
        d = known[name]()
        self.devices.insert(len(self.devices) if index in (None, -1) else index, d)

    def create_midi_clip(self, start, length):
        c = Clip(length)
        c.start_time = start
        self.arrangement_clips.append(c)

    def create_audio_clip(self, path, position):
        c = Clip(4.0, midi=False, file_path=path)
        c.start_time = position
        self.arrangement_clips.append(c)

    def duplicate_clip_to_arrangement(self, clip, time):
        import copy
        c = copy.deepcopy(clip)
        c.start_time = time
        self.arrangement_clips.append(c)


class Scene:
    def __init__(self, name=""):
        self.name, self.tempo, self.is_empty, self.fired = name, -1, True, 0

    def fire(self):
        self.fired += 1


class View:
    def __init__(self):
        self.selected_track = None
        self.selected_scene = None

    def select_device(self, d):
        self.selected_device = d


class Song:
    def __init__(self):
        self.tempo, self.is_playing, self.current_song_time = 120.0, False, 0.0
        self.signature_numerator, self.signature_denominator = 4, 4
        self.loop, self.loop_start, self.loop_length, self.metronome = False, 0.0, 16.0, False
        self.record_mode, self.session_record, self.arrangement_overdub = False, False, False
        self.root_note, self.scale_name = 0, "Major"
        self.scenes = [Scene() for _ in range(4)]
        self.return_tracks = [Track("A-Reverb", False, 0, 2), Track("B-Delay", False, 0, 2)]
        self.tracks = [Track("1-MIDI", True, 4, 2), Track("2-Audio", False, 4, 2)]
        self.master_track = Track("Main", False, 0, 0)
        self.view = View()
        self.cue_points = []
        self.undone = 0

    def start_playing(self):
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False

    continue_playing = start_playing

    def stop_all_clips(self):
        pass

    def undo(self):
        self.undone += 1

    def redo(self):
        self.undone -= 1

    def create_midi_track(self, i):
        t = Track("MIDI", True, len(self.scenes), len(self.return_tracks))
        self.tracks.insert(len(self.tracks) if i < 0 else i, t)

    def create_audio_track(self, i):
        t = Track("Audio", False, len(self.scenes), len(self.return_tracks))
        self.tracks.insert(len(self.tracks) if i < 0 else i, t)

    def create_return_track(self):
        self.return_tracks.append(Track("Return", False, 0, 0))

    def delete_track(self, i):
        del self.tracks[i]

    def delete_return_track(self, i):
        del self.return_tracks[i]

    def duplicate_track(self, i):
        import copy
        self.tracks.insert(i + 1, copy.deepcopy(self.tracks[i]))

    def create_scene(self, i):
        self.scenes.insert(len(self.scenes) if i < 0 else i, Scene())
        for t in self.tracks:
            t.clip_slots.insert(len(t.clip_slots) if i < 0 else i, ClipSlot())

    def delete_scene(self, i):
        del self.scenes[i]


class BrowserItem:
    def __init__(self, name, children=(), loadable=False):
        self.name, self.children, self.is_loadable = name, list(children), loadable
        self.is_folder = bool(children)
        self.uri = "query:" + name


class Browser:
    def __init__(self, song):
        self.song = song
        self.instruments = BrowserItem("Instruments", [BrowserItem("Drift", [BrowserItem("Pad.adv", loadable=True)], True)])
        self.audio_effects = BrowserItem("Audio Effects", [BrowserItem("EQ Eight", loadable=True), BrowserItem("Reverb", loadable=True)])
        self.loaded = []

    def load_item(self, item):
        self.loaded.append(item.name)
        self.song.view.selected_track.devices.append(Device(item.name, item.name.replace(" ", ""), []))


class Application:
    def __init__(self, song):
        self.browser = Browser(song)
