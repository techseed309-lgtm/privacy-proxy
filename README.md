# privacy-proxy

A small local tool that hides personal data in a document **before** it goes to a chatbot, and puts the real values
back into the chatbot's answer **after** it comes back. Built from scratch on an ordinary laptop (no GPU) for the
Signal & Byte **Build Lab** episode.

> **Not safe for real personal data.** On a fresh set of 100 synthetic letters the latest version (v4) still leaks
> something in 7 of them. Research benchmarks ask for 2 or fewer. Read [RESULTS.md](RESULTS.md) before you use it for
> anything, and test it on fake documents first.

## How it works
```
document ──mask──▶ masked text ──send──▶ chatbot ──answer──▶ restore ──▶ answer with real values
              │                                                  ▲
              └──────────── the list (tag → real value) ─────────┘   stays on your machine
```
- Every personal detail becomes a tag: `[NAME_1]`, `[ORG_1]`, `[CARD_1]` ...
- The same value always gets the same tag, so the chatbot can still tell people apart.
- Only the masked text is sent. The list of tags never leaves the machine.

Detector versions, kept side by side so every result can be repeated:

| Version | Adds |
|---|---|
| v1 | patterns + checksums: email, UK mobile, postcode, card (Luhn), IBAN (mod 97), NHS number (mod 11), NI number |
| v2 | a small local name model (spaCy `en_core_web_md`): people, organisations, places |
| v3 | "follow the thread": once a person is found, hide every later mention (surname, first name, title + surname, initials); street lines; patterns beat the model on overlap; form labels left alone |
| v4 | the value after a person field (`Tenant:`, `Patient:`, `Next of kin:` ...) is a person; a capitalised word before a known surname is the first name |

## Files
| File | What it does | Uses the internet? |
|---|---|---|
| `gen_docs.py` | makes synthetic UK letters (HR, clinic, tenancy, complaint, invoice) with an answer key per letter | no |
| `leak_test.py` | masks every letter with one version and counts what is still readable | no |
| `proxy.py` | the proxy: `mask(text, version)` and `restore(answer, vault)` | no |
| `round_trip.py` | masks letters, sends ONLY the masked text to Gemini, restores the answer, logs everything | yes (Gemini API) |

## Run it
```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_md

# 1. make a pile of fake letters
python gen_docs.py --n 100 --seed 20261029 --out testdocs/set3
# 2. leak test (offline)
python leak_test.py --docs testdocs/set3 --version v4 --log runs/v4-set3.json
# 3. mask one letter and see the tags + the list
python proxy.py testdocs/set3/doc_000.txt v4
# 4. round trip to Gemini (needs your own key in an environment variable; it is never printed)
export GEMINI_API_KEY=...         # PowerShell: $env:GEMINI_API_KEY="..."
python round_trip.py --docs testdocs/set3 --version v4 --n 20 --prompt keep --log runs/rt-keep.json
```
The seeds in [RESULTS.md](RESULTS.md) regenerate exactly the letters we tested.

## Known open bugs
1. **Fragments:** "card ending 2418" in a subject line is not hidden, and `leak_test.py` doesn't count it (it only
   looks for whole numbers). Gemini repeated the four digits in its reply.
2. **One person, two tags:** a sign-off with only the first name ("Yusuf") is hidden, but under a new tag, so the
   chatbot thinks there are two people.
3. Organisation names on a line of their own, and names typed in lower case, still leak.

## Checklist
See [CHECKLIST.md](CHECKLIST.md): what to check before you trust any tool like this.

## Credits
Prompted by *Reversible Pseudonymisation of Documents Sent to External LLMs: an Open Bilingual Benchmark and an Engine*
(arXiv 2610.34012, 25 Oct 2026). This repo is an independent build, not that paper's engine.

MIT licence. All test data is synthetic; never commit real personal data to this repo.
