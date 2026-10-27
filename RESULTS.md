# Results (real runs, 27 Oct 2026)

All letters are synthetic, made by `gen_docs.py` (noise 0.5). Laptop: Intel i5-8365U, 16 GB, no GPU.
A letter **leaks** when any personal value from its answer key is still readable after masking: the digits of a
number (whatever the separators), any part of a name of 3+ letters as a whole word, a street line or postcode, or an
organisation / email / NI number as written.

| Pile | Command | Note |
|---|---|---|
| set1 | `gen_docs.py --n 60 --seed 20261027` | v2 and v3 were built while looking at this pile |
| set2 | `gen_docs.py --n 100 --seed 20261028` | unseen by v1-v3; v4's fixes were made on it |
| set3 | `gen_docs.py --n 100 --seed 20261029` | unseen by every version |

## Leak tests
| Version | Pile | Letters leaking | Values leaked | What leaked | Time |
|---|---|---|---|---|---|
| v1 | set1 | **60 / 60** | 358 / 540 | names, organisations, street lines; 0 numbers | 2.2 s |
| v2 | set1 | 39 / 60 | 84 / 540 | names 52, street lines 27, orgs 5 | 6.8 s |
| v3 | set1 | 16 / 60 | 24 / 540 | names 21, orgs 3 | 6.4 s |
| v2 | set2 (unseen) | 55 / 100 | 91 / 900 | names 47, street lines 41, orgs 3 | 10.7 s |
| v3 | set2 (unseen) | 11 / 100 | 13 / 900 | names 10, orgs 3 | 7.6 s |
| v4 | set2 (fixes made here) | 4 / 100 | 5 / 900 | names 2, orgs 3 | 7.1 s |
| v3 | set3 (unseen) | 21 / 100 | 29 / 886 | names 23, orgs 6 | 10.4 s |
| **v4** | **set3 (unseen)** | **7 / 100** | 8 / 886 | orgs 6, names 2 | 6.9 s |

The paper that prompted this build (arXiv 2610.34012) sets a bar of a leak in at most 2 % of documents. **v4 does not
meet it.** Note how v3 scored 11 on one unseen pile and 21 on another: score every change on a pile it has never seen.

## Round trip with Gemini (`gemini-flash-latest`, set3, v4, first 20 letters)
| Prompt | Letters | Tags in answers, restored | Altered | Invented | Values readable in what was sent |
|---|---|---|---|---|---|
| plain: "summary + short reply letter" | 20 | 221 / 221 | 0 | 0 | 0 |
| keep: the same + "copy the placeholders exactly, don't invent new ones" | 20 | 293 / 293 | 0 | 0 | 0 |

- These 20 letters contain none of v4's 7 leaking letters, so "0 sent" holds for this sample, not for v4 in general.
- The keep line made no difference to survival; its answers used more tags.
- 40 answers is a small sample; the paper reports invented tags with some local models.
- With the plain prompt Gemini repeated an unmasked fragment ("card ending in 2418") twice (open bug 1).

## What we got wrong on the way (kept on purpose)
- Blamed the v3 form-label filter for "Tenant: Eilidh [NAME_1]". The raw model output showed the name in that field was
  never tagged at all; only "Dear Mrs Okafor" was, so the thread hid the surname only. Fixed in v4.
- Our first round-trip score counted 2 "altered" tags; both were the restored real card number. Fixed the check.

## Limits
Own generator (5 templates), UK English only, fixes made after looking at leaks (hence the unseen piles), small
round-trip sample. Real paperwork is messier.
