"""Leak test: mask every test document with one proxy version and count what still gets through.

A value LEAKS when any of it is still readable in the cleaned text:
  numbers (card, NHS, IBAN, phone) - the digits survive, whatever separators are around them
  names - the full name, or any part of it of 3+ letters, as a whole word (case ignored)
  addresses - the street line or the postcode
  emails, organisations, NI numbers - the value itself (case ignored)

    python leak_test.py --docs testdocs/set1 --version v1 --log runs/01-v1-set1.json
"""
import argparse, glob, json, os, re, time

import proxy


def leaked(item, cleaned):
    t, v = item["type"], item["value"]
    low = cleaned.lower()
    if t in ("card", "nhs", "iban", "phone"):
        return v.upper() in re.sub(r"[ .\-]", "", cleaned.upper())
    if t == "name":
        parts = [v] + [p for p in v.split() if len(p) >= 3]
        return any(re.search(r"(?<!\w)" + re.escape(p.lower()) + r"(?!\w)", low) for p in parts)
    if t == "address":
        street, rest = v.split(",", 1)
        postcode = " ".join(rest.split()[-2:])
        return street.lower() in low or postcode.lower() in low
    return v.lower() in low


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--version", default="v2")
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    t0 = time.time()
    docs, by_type, leaky_docs = [], {}, 0
    for path in sorted(glob.glob(os.path.join(a.docs, "doc_*.txt"))):
        text = open(path, encoding="utf-8").read()
        meta = json.load(open(path[:-4] + ".gold.json", encoding="utf-8"))
        cleaned, vault = proxy.mask(text, a.version)
        leaks = [g for g in meta["gold"] if leaked(g, cleaned)]
        for g in meta["gold"]:
            s = by_type.setdefault(g["type"], {"values": 0, "leaked": 0})
            s["values"] += 1; s["leaked"] += g in leaks
        leaky_docs += bool(leaks)
        docs.append({"doc": os.path.basename(path), "kind": meta["kind"], "noisy": meta["noisy"],
                     "leaks": leaks, "placeholders": len(vault), "cleaned": cleaned})
    n = len(docs)
    total_v = sum(s["values"] for s in by_type.values()); total_l = sum(s["leaked"] for s in by_type.values())
    summary = {"version": a.version, "notes": proxy.VERSION_NOTES[a.version], "docs": n,
               "docs_with_a_leak": leaky_docs, "doc_leak_rate": round(leaky_docs / n, 3),
               "values": total_v, "values_leaked": total_l, "by_type": by_type,
               "noisy_docs_leaking": sum(1 for d in docs if d["noisy"] and d["leaks"]),
               "noisy_docs": sum(1 for d in docs if d["noisy"]),
               "seconds": round(time.time() - t0, 1), "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
    json.dump({"summary": summary, "docs": docs}, open(a.log, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
