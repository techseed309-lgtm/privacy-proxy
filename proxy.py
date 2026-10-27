"""privacy-proxy: hide personal data before a document goes to a chatbot, put it back in the answer.

    mask(text)      -> cleaned text + vault (placeholder -> real value), all local
    restore(answer) -> answer with the real values back in

Detector versions (kept side by side so every run in runs/ can be repeated):
    v1  patterns only: email, UK phone, postcode, card (Luhn), IBAN (mod 97), NHS number (mod 11), NI number
    v2  v1 + a local named-entity model (spaCy en_core_web_md): people, organisations, places
    v3  v2 + fixes from the v2 leak test (runs/02-v2-set1.json):
        - once a person or organisation is found, every later mention of it is hidden too: surname or first name
          alone, with a title ("Dr Price"), initials ("F. Gunn")
        - street lines ("169 Mill Lane") by pattern
        - pattern matches win over the model where they overlap (the model ate half a postcode)
        - form labels the model mistook for names ("Patient:", "Bill to:") are not masked
    v4  v3 + fixes from the v3 leak test on unseen set2 (runs/06-v3-set2.json). The model never tagged names that
        sit in form fields ("Tenant: Eilidh Okafor"), so propagation from "Mrs Okafor" hid the surname only:
        - a capitalised word right before a known surname is hidden as the first name
        - the value after a person field (Tenant:, Patient:, Queries:, Next of kin:, Bill to:, Name:) is a person
"""
import json, re, sys

VERSION_NOTES = {"v1": "patterns only", "v2": "patterns + spaCy NER",
                 "v3": "patterns + NER + propagation, streets, pattern priority, label filter",
                 "v4": "v3 + first name before a known surname + person form fields"}
PERSON_FIELD = re.compile(r"(?im)^(?:Tenant|Patient|Queries|Next of kin|Bill to|Name|Guarantor)\s*:\s*"
                          r"((?:[A-Z][\w'-]+|[a-z][\w'-]+)(?:\s+(?:[A-Z][\w'-]+|[a-z][\w'-]+)){1,2})(?=\s*(?:,|\n|$))")

SEP = r"[ .\-]?"


def luhn_ok(d):
    total = 0
    for i, c in enumerate(reversed(d)):
        n = int(c) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def nhs_ok(d):
    if len(d) != 10:
        return False
    check = 11 - sum(int(x) * w for x, w in zip(d[:9], range(10, 1, -1))) % 11
    return (0 if check == 11 else check) == int(d[9])


def iban_ok(s):
    s = re.sub(r"[^A-Z0-9]", "", s.upper())
    if len(s) < 15:
        return False
    num = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(num) % 97 == 1


PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
    ("IBAN", re.compile(r"\bGB\d{2}(?:" + SEP + r"[A-Z0-9]{4}){4}" + SEP + r"[A-Z0-9]{2}\b"), iban_ok),
    ("CARD", re.compile(r"\b\d{4}(?:" + SEP + r"\d{4}){3}\b"), lambda s: luhn_ok(re.sub(r"\D", "", s))),
    ("NHS", re.compile(r"\b\d{3}" + SEP + r"\d{3}" + SEP + r"\d{4}\b"), lambda s: nhs_ok(re.sub(r"\D", "", s))),
    ("PHONE", re.compile(r"\b07\d{3}" + SEP + r"\d{3}" + SEP + r"\d{3}\b"), None),
    ("NI", re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b"), None),
    ("POSTCODE", re.compile(r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s\d[A-Z]{2}\b"), None),
]

_nlp = None


def nlp():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_md")
    return _nlp


NER_MAP = {"PERSON": "NAME", "ORG": "ORG", "GPE": "PLACE", "FAC": "PLACE", "LOC": "PLACE"}


STREET = re.compile(r"\b\d{1,4}[A-Za-z]?\s+(?:[A-Z][a-z]+\s+){1,3}(?:Road|Street|Lane|Drive|Avenue|Close|Grove|Row|"
                    r"Terrace|Walk|Rise|Yard|Way|Court|Crescent|Place|Gardens|Square|Hill|Park|Mews)\b")
TITLES = r"(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?"


def mentions(text, full, label):
    """Every later mention of a person or organisation found once: the full form, and for people the surname or
    first name alone (3+ letters), with a title, or as initials + surname."""
    forms = [re.escape(full)]
    parts = full.split()
    if label == "NAME" and len(parts) >= 2:
        first, last = parts[0], parts[-1]
        forms += [TITLES + r"\s+" + re.escape(last), r"[A-Z]\.\s?" + re.escape(last), re.escape(last), re.escape(first)]
        forms += [r"\b" + first[0] + r"\." + last[0] + r"\."]
    out = []
    for f in forms:
        for m in re.finditer(r"(?<!\w)" + f + r"(?!\w)", text, flags=re.I if label == "NAME" else 0):
            if len(m.group().strip(".")) >= 3 or "." in m.group():
                out.append((m.start(), m.end(), label))
    return out


def detect(text, version="v2"):
    spans = []
    for label, rx, check in PATTERNS:
        for m in rx.finditer(text):
            if check is None or check(m.group()):
                spans.append((m.start(), m.end(), label))
    if version >= "v3":
        spans += [(m.start(), m.end(), "STREET") for m in STREET.finditer(text)]
    pattern_spans = list(spans)
    if version >= "v2":
        for ent in nlp()(text).ents:
            if ent.label_ not in NER_MAP:
                continue
            s, e, label = ent.start_char, ent.end_char, NER_MAP[ent.label_]
            if version >= "v3":
                if text[e:e + 1] == ":" or (" to" == text[e:e + 3] and text[e + 3:e + 4] == ":"):
                    continue  # a form label ("Patient:", "Bill to:"), not a person
                for ps, pe, _ in pattern_spans:  # trim the model's span off a pattern match
                    if ps < e and pe > s:
                        e = ps if s < ps else e
                        s = pe if s >= ps else s
                if e - s < 2 or not text[s:e].strip():
                    continue
                s += len(text[s:e]) - len(text[s:e].lstrip()); e -= len(text[s:e]) - len(text[s:e].rstrip())
                full = text[s:e]
                if label in ("NAME", "ORG") and len(full) >= 3:
                    spans += mentions(text, full, label)
            spans.append((s, e, label))
    if version >= "v4":
        for m in PERSON_FIELD.finditer(text):
            spans.append((m.start(1), m.end(1), "NAME"))
            spans += mentions(text, m.group(1), "NAME")
        surnames = {text[s:e].split()[-1] for s, e, l in spans if l == "NAME" and text[s:e].split()}
        for last in surnames:
            if len(last) < 3 or not last[0].isupper():
                continue
            for m in re.finditer(r"(?<![\w.])([A-Z][a-z]{2,})\s+" + re.escape(last) + r"(?!\w)", text):
                if not re.fullmatch(TITLES, m.group(1)) and m.group(1) not in ("Dear", "The", "From", "Thanks"):
                    spans.append((m.start(), m.end(), "NAME"))
    # longest span wins where spans overlap
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    out, end = [], -1
    for s in spans:
        if s[0] >= end:
            out.append(s); end = s[1]
    return out


def norm(label, value):
    if label in ("CARD", "NHS", "PHONE", "IBAN"):
        return re.sub(r"[^A-Z0-9]", "", value.upper())
    return value.strip().lower()


def mask(text, version="v2"):
    vault, seen, counts, pieces, last = {}, {}, {}, [], 0
    for start, end, label in detect(text, version):
        key = (label, norm(label, text[start:end]))
        if key not in seen:
            counts[label] = counts.get(label, 0) + 1
            seen[key] = f"[{label}_{counts[label]}]"
            vault[seen[key]] = text[start:end]
        pieces.append(text[last:start]); pieces.append(seen[key]); last = end
    pieces.append(text[last:])
    return "".join(pieces), vault


PLACEHOLDER = re.compile(r"\[\s*([A-Z]+)[ _]?(\d+)\s*\]")


def restore(answer, vault):
    """Put the real values back. Returns (restored text, issued placeholders restored, invented placeholders)."""
    restored, invented = set(), []

    def sub(m):
        key = f"[{m.group(1)}_{m.group(2)}]"
        if key in vault:
            restored.add(key); return vault[key]
        invented.append(m.group(0)); return m.group(0)

    return PLACEHOLDER.sub(sub, answer), restored, invented


if __name__ == "__main__":
    text = open(sys.argv[1], encoding="utf-8").read()
    cleaned, vault = mask(text, sys.argv[2] if len(sys.argv) > 2 else "v2")
    print(cleaned); print(json.dumps(vault, ensure_ascii=False, indent=1))
