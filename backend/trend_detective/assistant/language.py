"""Reply language: Ukrainian or English only (team decision 2026-11-15).

Decided by code, not by the model: a question with Ukrainian-specific letters (і ї є ґ) gets a
Ukrainian answer; everything else gets English. Russian (Cyrillic with ы э ъ ё and no Ukrainian
letters) and any other language also get English, with a one-line note that the assistant answers
in English or Ukrainian.
"""

from __future__ import annotations

import re

UK_ONLY = re.compile(r"[іїєґІЇЄҐ]")
RU_ONLY = re.compile(r"[ыэъёЫЭЪЁ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
CYRILLIC_WORD = re.compile(r"[Ѐ-ӿ]+")
# frequent question and function words that differ between Russian and Ukrainian
RU_WORDS = {
    "как",
    "что",
    "почему",
    "где",
    "это",
    "или",
    "ли",
    "мне",
    "мой",
    "она",
    "он",
    "они",
    "есть",
    "какой",
    "какая",
    "сколько",
    "когда",
    "здесь",
    "очень",
    "меняется",
    "украине",
    "в",
}
UK_WORDS = {
    "як",
    "що",
    "чому",
    "де",
    "це",
    "або",
    "чи",
    "мені",
    "мій",
    "вона",
    "він",
    "вони",
    "є",
    "який",
    "яка",
    "скільки",
    "коли",
    "тут",
    "дуже",
    "так",
    "змінюється",
    "україні",
    "у",
}
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
# common English words: a Latin-script question without any of them is probably another language
EN_HINTS = re.compile(
    r"\b(the|is|are|was|what|why|how|where|when|which|does|do|in|of|and|or|to|my|this|it|can|show|"
    r"compare|explain|trend|warming|drying|rain|soil|water|temperature)\b",
    re.IGNORECASE,
)


def reply_language(text: str) -> tuple[str, bool]:
    """(language, other) for a question: language is "uk" or "en"; ``other`` is True when the
    question seems to be in a third language (the answer is then English with a short note)."""
    if UK_ONLY.search(text):
        return "uk", False
    if CYRILLIC.search(text):
        # Cyrillic without Ukrainian letters: Russian-only letters, or more Russian than Ukrainian
        # function words, mean Russian (answered in English); otherwise Ukrainian (short Ukrainian
        # phrases can lack і/ї/є/ґ, e.g. "Чому так тепло?")
        if RU_ONLY.search(text):
            return "en", True
        words = CYRILLIC_WORD.findall(text.lower())
        ru = sum(w in RU_WORDS for w in words)
        uk = sum(w in UK_WORDS for w in words)
        return ("en", True) if ru > uk else ("uk", False)
    if LATIN_WORD.search(text) and not EN_HINTS.search(text) and len(text.split()) >= 3:
        return "en", True
    return "en", False


def instruction(lang: str, other: bool) -> str:
    if lang == "uk":
        return (
            "REPLY LANGUAGE: Ukrainian (українська). Write the answer and every suggestion's `why` "
            "in Ukrainian; translate the cautious wording faithfully, never stronger."
        )
    note = (
        (
            " The question is not in English or Ukrainian: start with one short line saying that you "
            "answer in English or Ukrainian (in English), then answer in English."
        )
        if other
        else ""
    )
    return "REPLY LANGUAGE: English. Write the answer and every suggestion's `why` in English." + note
