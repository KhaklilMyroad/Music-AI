"""Words into what is sung: syllables, which of them is stressed, and how each one sounds.

Spanish is done by its spelling rules, which are regular. English needs a pronouncing dictionary (the optional
`cmudict` package); without it syllables are counted from the spelling and marked as an estimate. In any language a
word typed with hyphens ("sha-lom") is taken exactly as typed, and a lone "-" or "+" means: this note goes on with
the syllable before it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HOLD = {"-", "+", "_"}
END_MARKS = ",.;:!?…"


@dataclass
class Syllable:
    text: str                       # the letters sung on this note: "twin", "kle"
    word: str = ""
    index: int = 1                  # place in the word, from 1
    count: int = 1                  # syllables in the word
    phonemes: list[str] = field(default_factory=list)
    stressed: bool | None = None    # None: not known
    line: int = 0                   # lyric line, from 0
    hold: bool = False              # not a syllable: the note carries on the previous one
    breath_after: bool = False      # a comma, a full stop or the end of the line follows
    sure: bool = True               # False: counted from the spelling, the word is not in the dictionary


# ------------------------------------------------------------------------------------------- Spanish

_ES_STRONG, _ES_WEAK, _ES_WEAK_ACC = "aeoáéó", "iuü", "íú"
_ES_VOWELS = _ES_STRONG + _ES_WEAK + _ES_WEAK_ACC
_ES_ONSETS = {"pr", "br", "tr", "dr", "cr", "gr", "fr", "pl", "bl", "cl", "gl", "fl", "kr", "kl"}
_ES_UNITS = ("ch", "ll", "rr")      # two letters, one consonant


def _es_units(word: str) -> list[str]:
    """Letters grouped the way Spanish counts them: ch, ll, rr are one consonant; the u of que/qui/gue/gui is silent
    and stays with its consonant; a final y is the vowel i."""
    out, i = [], 0
    while i < len(word):
        two = word[i:i + 2]
        if two in _ES_UNITS:
            out.append(two)
            i += 2
        elif two in ("qu", "gu") and i + 2 < len(word) and word[i + 2] in "eiéí":
            out.append(two)
            i += 2
        else:
            out.append(word[i])
            i += 1
    return out


def _es_is_vowel(units: list[str], i: int) -> bool:
    u = units[i]
    if u == "y":
        return i == len(units) - 1 or not _es_is_vowel(units, i + 1)      # hoy, muy, y; but yo, playa
    return len(u) == 1 and u in _ES_VOWELS


def spanish_syllables(word: str) -> list[str]:
    units = _es_units(word.lower())
    vowel = [_es_is_vowel(units, i) for i in range(len(units))]
    if not any(vowel):
        return [word]
    # nuclei: runs of vowels, cut where two vowels do not share a syllable (two strong ones, or an accented weak one)
    nuclei: list[list[int]] = []
    for i, v in enumerate(vowel):
        if not v:
            continue
        if nuclei and nuclei[-1][-1] == i - 1:
            a, b = units[i - 1], units[i]
            hiatus = (a in _ES_STRONG and b in _ES_STRONG) or a in _ES_WEAK_ACC or b in _ES_WEAK_ACC
            if not hiatus:
                nuclei[-1].append(i)
                continue
        nuclei.append([i])
    bounds = [0]                                    # index of the first unit of every syllable
    for a, b in zip(nuclei, nuclei[1:]):
        cons = list(range(a[-1] + 1, b[0]))
        k = len(cons)
        if k <= 1:
            cut = b[0] - k
        elif "".join(units[c] for c in cons[-2:]) in _ES_ONSETS:
            cut = cons[-2]                          # a-bra-zo, ins-truc-ción
        else:
            cut = cons[-1]                          # can-tar, ins-tan-te
        bounds.append(cut)
    bounds.append(len(units))
    out, at = [], 0
    for a, b in zip(bounds, bounds[1:]):            # the pieces in the word's own capitals
        size = sum(len(u) for u in units[a:b])
        out.append(word[at:at + size])
        at += size
    return out


def spanish_stress(syllables: list[str]) -> int:
    """Index of the stressed syllable: the one with a written accent; else the last but one when the word ends in a
    vowel, n or s; else the last."""
    for i, s in enumerate(syllables):
        if any(c in "áéíóú" for c in s.lower()):
            return i
    if len(syllables) == 1:
        return 0
    return len(syllables) - 2 if syllables[-1][-1].lower() in "aeiouns" else len(syllables) - 1


_ES_PLAIN = dict(zip("áéíóúü", "aeiouu"))


def spanish_phonemes(syllable: str, word_start: bool = False) -> list[str]:
    """Latin-American Spanish in plain symbols (x = the j of 'jota', y = ll, ny = ñ, rr = the rolled r). Every
    singing engine names its phonemes its own way: these are for reading and for an adapter to translate."""
    s = syllable.lower()
    out, i = [], 0
    while i < len(s):
        c, nxt = s[i], s[i + 1:i + 2]
        if c in _ES_PLAIN or c in "aeiou":
            out.append(_ES_PLAIN.get(c, c))
        elif c == "c":
            if nxt == "h":
                out.append("ch")
                i += 1
            else:
                out.append("s" if nxt and nxt in "eiéí" else "k")
        elif c == "q":
            out.append("k")
            i += nxt == "u"
        elif c == "g":
            if nxt == "u" and s[i + 2:i + 3] and s[i + 2] in "eiéí":
                out.append("g")
                i += 1
            else:
                out.append("x" if nxt and nxt in "eiéí" else "g")
        elif c == "l":
            if nxt == "l":
                out.append("y")
                i += 1
            else:
                out.append("l")
        elif c == "r":
            if nxt == "r":
                out.append("rr")
                i += 1
            else:
                out.append("rr" if word_start and i == 0 else "r")
        elif c == "y":
            out.append("i" if i == len(s) - 1 or (nxt and nxt not in _ES_VOWELS) else "y")
        elif c == "x":
            out += ["k", "s"]
        elif c == "h":
            pass
        else:
            out.append({"v": "b", "z": "s", "j": "x", "ñ": "ny"}.get(c, c))
        i += 1
    return out


# ------------------------------------------------------------------------------------------- English

_EN_ONSETS = {
    "P L", "P R", "B L", "B R", "T R", "D R", "K L", "K R", "G L", "G R", "F L", "F R", "TH R", "SH R", "S P", "S T", "S K", "S M",
    "S N", "S L", "S W", "S F", "T W", "D W", "K W", "G W", "P Y", "B Y", "K Y", "F Y", "M Y", "HH Y", "V Y", "S P L", "S P R",
    "S T R", "S K R", "S K W", "S K Y",
}
_cmu = None


def _dictionary():
    """The CMU pronouncing dictionary, if the optional package is installed. {} if not."""
    global _cmu
    if _cmu is None:
        try:
            import cmudict
            _cmu = cmudict.dict()
        except Exception:
            _cmu = {}
    return _cmu


def english_pronunciation(word: str) -> list[list[str]] | None:
    """The word's phonemes (ARPAbet) grouped by syllable, or None if the word is not in the dictionary. Consonants
    between two vowels go to the later syllable as far as they can start an English syllable (twin-kle, not twi-nkle)."""
    said = _dictionary().get(word.lower().replace("’", "'"))
    if not said:
        return None
    ph = said[0]
    vowels = [i for i, p in enumerate(ph) if p[-1].isdigit()]
    if not vowels:
        return [list(ph)]
    cuts = [0]
    for a, b in zip(vowels, vowels[1:]):
        cons = ph[a + 1:b]
        take = 0
        for k in range(len(cons), 0, -1):
            if k == 1 and cons[-1] != "NG" or " ".join(cons[-k:]) in _EN_ONSETS:
                take = k
                break
        cuts.append(b - take)
    cuts.append(len(ph))
    return [list(ph[a:b]) for a, b in zip(cuts, cuts[1:])]


def _vowel_groups(word: str) -> list[tuple[int, int]]:
    return [m.span() for m in re.finditer(r"[aeiouyáéíóúü]+", word.lower())]


def estimate_english_count(word: str) -> int:
    """Syllables guessed from the spelling: vowel groups, less a silent final e. An estimate, marked as one."""
    w = word.lower()
    n = len(_vowel_groups(w))
    if n > 1 and w.endswith("e") and not w.endswith(("le", "ee", "ie", "ue", "oe", "ye")):
        n -= 1
    if n > 1 and w.endswith(("ed", "es")) and w[-3:-2] not in ("t", "d", "s", "x", "z") and w[-3] not in "aeiouy":
        n -= 1
    return max(1, n)


def split_spelling(word: str, count: int, lang: str = "en_US") -> list[str]:
    """The word's letters cut into `count` pieces to print under the notes. Hyphenation patterns (the optional
    `pyphen` package) when they give that many pieces, else a cut before the consonant ahead of each vowel group.
    When neither gives `count` pieces the result is word#1, word#2..., which is honest about not knowing."""
    if count <= 1:
        return [word]
    try:
        import pyphen
        parts = pyphen.Pyphen(lang=lang).inserted(word).split("-")
        if len(parts) == count:
            return parts
    except Exception:
        pass
    groups = _vowel_groups(word)
    if len(groups) == count + 1 and word.lower().endswith("e"):
        groups = groups[:-1]
    if len(groups) == count:
        cuts = [0]
        for (_, a_end), (b_start, _) in zip(groups, groups[1:]):
            cons = b_start - a_end
            cuts.append(b_start - 1 if cons >= 1 else b_start)
        cuts.append(len(word))
        return [word[a:b] for a, b in zip(cuts, cuts[1:])]
    return [f"{word}#{i + 1}" for i in range(count)]


# ------------------------------------------------------------------------------------------- any text

def word_syllables(word: str, lang: str) -> list[Syllable]:
    """One word as its sung syllables. A word typed with hyphens is taken as typed."""
    typed = [p for p in word.split("-") if p]
    whole = "".join(typed)
    if lang == "es":
        parts = typed if len(typed) > 1 else spanish_syllables(whole)
        stress = spanish_stress(parts)
        return [Syllable(p, whole, i + 1, len(parts), spanish_phonemes(p, i == 0), i == stress if len(parts) > 1 else None)
                for i, p in enumerate(parts)]
    if lang == "en":
        said = english_pronunciation(whole)
        if said is not None and (len(typed) <= 1 or len(typed) == len(said)):
            parts = typed if len(typed) > 1 else split_spelling(whole, len(said))
            # a one-syllable word carries no stress to place: "the" and "star" both count as free
            return [Syllable(p, whole, i + 1, len(said), [x.rstrip("012") for x in ph],
                             any(x.endswith("1") for x in ph) if len(said) > 1 else None)
                    for i, (p, ph) in enumerate(zip(parts, said))]
        if len(typed) > 1:
            return [Syllable(p, whole, i + 1, len(typed), sure=False) for i, p in enumerate(typed)]
        n = estimate_english_count(whole)
        return [Syllable(p, whole, i + 1, n, sure=False) for i, p in enumerate(split_spelling(whole, n))]
    return [Syllable(p, whole, i + 1, len(typed)) for i, p in enumerate(typed)]       # as typed: one syllable per piece


def parse(text: str, lang: str = "en") -> list[Syllable]:
    """Lyrics as a flat list of syllables and holds, each knowing its line and whether a breath can follow it."""
    out: list[Syllable] = []
    line_no = 0
    for raw in text.replace("/", "\n").splitlines():
        tokens = raw.split()
        if not tokens:
            continue
        for tok in tokens:
            core = tok.strip("\"'“”‘’()[]¡¿" + END_MARKS)
            if tok in HOLD or core in HOLD:
                out.append(Syllable(tok, line=line_no, hold=True))
                continue
            core = re.sub(r"[^\w'’\-]", "", core).strip("-")
            if not core:
                continue
            sylls = word_syllables(core, lang)
            for s in sylls:
                s.line = line_no
            sylls[-1].breath_after = tok.rstrip("\"'”’)]")[-1:] in END_MARKS
            out += sylls
        if out:
            out[-1].breath_after = True
        line_no += 1
    return out
