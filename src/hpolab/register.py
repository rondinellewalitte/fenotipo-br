"""Register of each gold item in a vignette: does the note use the HPO term itself, or only
other words? (Exp 03, PREREG Desvios.)

An item is *technical* where the note contains its official PT label or a close cognate of
its English label: every content word of that form has a fuzzy match (ratio >= MIN_RATIO on
folded text) among the words of one sentence. English words are first respelled the way
Portuguese writes Greek/Latin roots (ph -> f, y -> i, -osis -> -ose, ...).

    lay        no technical form anywhere in the note
    technical  the generator's phrase for the item is itself technical
    both       the phrase is not technical, but a technical form occurs elsewhere

Known blind spot: a lay mention elsewhere next to a technical phrase is not detected, so
some 'both' items are counted as 'technical'. The pilot manual check measures it.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from hpolab.retrieval import fold

MIN_RATIO = 80
MIN_TOKEN_LEN = 3

EN_STOPWORDS = frozenset(
    "of the and with in on to at for by from or a an abnormal abnormality abnormally "
    "morphology finding findings".split()
)
PT_STOPWORDS = frozenset(
    "de da do das dos e em na no nas nos com a o as os para por um uma ao aos pelo pela "
    "anormal anormalidade anomalia alteracao alterado alterada morfologia".split()
)
# Direction words collapse to one token in both languages, so "reduzida" matches "reduced"
# and "diminuida".
DIRECTION = {
    **dict.fromkeys(
        "increased elevated high large big aumentado aumentada aumentados aumentadas "
        "elevado elevada elevados elevadas alto alta altos altas grande grandes".split(),
        "+",
    ),
    **dict.fromkeys(
        "decreased reduced low small diminished reduzido reduzida reduzidos reduzidas "
        "diminuido diminuida diminuidos diminuidas baixo baixa baixos baixas pequeno pequena "
        "pequenos pequenas".split(),
        "-",
    ),
}
# English spelling -> Portuguese spelling of Greek/Latin roots, applied in order.
_RESPELL = [
    (r"^s([bcdfgklmnpqrtv])", r"es\1"),  # scoliosis -> escoliosis
    (r"tion$", "cao"),
    (r"ity$", "idade"),
    (r"osis$", "ose"),
    (r"itis$", "ite"),
    (r"ism$", "ismo"),
    (r"ous$", "oso"),
    (r"ic$", "ico"),
    (r"(ph|th|ch|rh)y$", r"\1ia"),  # myopathy -> myopathia, dysplasy
    (r"([lmn])y$", r"\1ia"),  # microcephaly -> microcephalia
    (r"ph", "f"),
    (r"th", "t"),
    (r"rh", "r"),
    (r"ch", "c"),
    (r"ae|oe", "e"),
    (r"k", "c"),
    (r"y", "i"),
    (r"([lmnpt])\1", r"\1"),  # intellectual -> intelectual
]
_SENTENCE_RE = re.compile(r"[.!?;\n]+")


def respell(word: str) -> str:
    for pat, rep in _RESPELL:
        word = re.sub(pat, rep, word)
    return word


def _tokens(text: str) -> list[str]:
    return [DIRECTION.get(w, w) for w in fold(text).split()]


def content_tokens(label: str, lang: str) -> list[str]:
    stop = EN_STOPWORDS if lang == "en" else PT_STOPWORDS
    out = []
    for w in _tokens(label):
        if w in stop or (len(w) < MIN_TOKEN_LEN and w not in "+-"):
            continue
        out.append(respell(w) if lang == "en" and w not in "+-" else w)
    return out


def form_in(tokens: list[str], sentence: str) -> bool:
    """Every content token of a term form has a fuzzy match among the sentence's words."""
    words = _tokens(sentence)
    return bool(tokens) and all(
        any(t == w or (len(t) > 2 and fuzz.ratio(t, w) >= MIN_RATIO) for w in words) for t in tokens
    )


def technical_sentence(text: str, forms: list[list[str]]) -> str | None:
    """First sentence of `text` that contains one of the term forms, or None."""
    for sentence in _SENTENCE_RE.split(text):
        if any(form_in(f, sentence) for f in forms):
            return sentence.strip()
    return None


def classify(text: str, phrase: str, label_en: str, label_pt: str | None) -> dict:
    forms = [content_tokens(label_en, "en")]
    if label_pt:
        forms.append(content_tokens(label_pt, "pt"))
    forms = [f for f in forms if f]
    hit = technical_sentence(text, forms)
    phrase_hit = technical_sentence(phrase, forms) is not None
    if hit is None:
        register = "lay"
    elif phrase_hit:
        register = "technical"
    else:
        register = "both"
    return {"register": register, "technical_sentence": hit or ""}
