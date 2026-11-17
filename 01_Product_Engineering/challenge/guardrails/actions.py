import re
import unicodedata

from nemoguardrails.actions import action

PROMISE = re.compile(r"\b(zajamcen|garantiran|guarantee)")
AVAILABLE = re.compile(r"\boptika je dostupna|\bima optike|\boptika je tu\b")
NO_FIBRE = re.compile(r"\bnema (ni )?optik|\boptika nije dostupna|\boptike nema")
NO_PROJECT = re.compile(r"\bnema (ni )?projekta\b|\bprojekta nema\b|\bbez projekta\b|\bprojekt ne postoji")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower().replace("đ", "d"))
    return "".join(c for c in text if not unicodedata.combining(c))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:[./_-][a-z0-9]+)*", _fold(text)))


def unsupported(answer: str, records: str) -> str:
    text, facts, known = _fold(answer), _fold(records), _tokens(records)
    parts = {part for token in known for part in re.split(r"[./_-]", token)}
    for token in _tokens(answer):
        if any(c.isdigit() for c in token) and token not in known and not (token.isdigit() and token in parts):
            return f"{token} is not in the records"
    connected = "status: homes connected" in facts
    if PROMISE.search(text):
        return "a promise Fiberly never makes"
    if AVAILABLE.search(text) and not connected and not AVAILABLE.search(facts):
        return "fibre available, against the status"
    if connected and NO_FIBRE.search(text):
        return "no fibre, against HOMES CONNECTED"
    if re.search(r"naziv projekta: (ftth|eubb)_", facts) and NO_PROJECT.search(text):
        return "no project, against the project named"
    return ""


@action(name="check_facts")
async def check_facts(text: str, records: str = "") -> bool:
    return not unsupported(text, records)
