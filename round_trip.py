"""Round trip: masked document -> Gemini -> answer -> restore locally. Logs exactly what left the laptop.

For each document: mask it, send ONLY the cleaned text to Gemini with a task (summary + short reply letter),
restore the answer, and count
  issued      placeholders in the answer that came back intact and were restored
  altered     placeholder-like strings the model changed (e.g. NAME_1 without brackets, [Name 1]) left unrestored
  invented    placeholders the model made up (never issued)
  payload_leaks   gold values still readable in what was SENT (must be 0 for the documents the proxy cleans fully)

    python round_trip.py --docs testdocs/set1 --version v2 --n 20 --prompt plain --log runs/03-rt-v2-plain.json
The API key is read from the environment variable GEMINI_API_KEY (or GEMINI_API_KEY_<n> with --key n) and never
printed or logged. Only the masked text is sent.
"""
import argparse, glob, json, os, re, time

import proxy
from leak_test import leaked

PROMPTS = {
    "plain": "Read this document. Write a three-sentence summary, then a short reply letter to the person it is about.",
    "keep": ("Read this document. Write a three-sentence summary, then a short reply letter to the person it is about. "
             "The document contains placeholders in square brackets such as [NAME_1]; copy them exactly as written, "
             "brackets included, wherever you refer to that item, and do not invent new ones."),
}
# a placeholder the model changed: bracketed in another spelling ("[Name 1]") or bare with an underscore ("NAME_1");
# a restored real value such as "card 4543..." must not count
LABELS = r"(?:NAME|ORG|PLACE|STREET|EMAIL|PHONE|IBAN|CARD|NHS|NI|POSTCODE)"
LOOSE = re.compile(r"\[\s*" + LABELS + r"[ _-]?\d+\s*\]|\b" + LABELS + r"_\d+\b", re.I)


def key(n):
    name = "GEMINI_API_KEY" + ("" if n == 1 else f"_{n}")
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"set the environment variable {name} first")
    return value


def PLACEHOLDER_KEYS(sent):
    return [f"[{m.group(1)}_{m.group(2)}]" for m in proxy.PLACEHOLDER.finditer(sent)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--version", default="v2")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--prompt", default="plain", choices=PROMPTS)
    ap.add_argument("--model", default="gemini-flash-latest")
    ap.add_argument("--key", type=int, default=1)
    ap.add_argument("--log", required=True)
    ap.add_argument("--resume", action="store_true", help="keep the rows already in --log, run only missing docs")
    a = ap.parse_args()
    from google import genai
    client = genai.Client(api_key=key(a.key))
    rows = json.load(open(a.log, encoding="utf-8"))["rows"] if a.resume and os.path.exists(a.log) else []
    done_docs = {r["doc"] for r in rows}
    for path in sorted(glob.glob(os.path.join(a.docs, "doc_*.txt")))[: a.n]:
        if os.path.basename(path) in done_docs:
            continue
        text = open(path, encoding="utf-8").read()
        gold = json.load(open(path[:-4] + ".gold.json", encoding="utf-8"))["gold"]
        cleaned, vault = proxy.mask(text, a.version)
        payload_leaks = [g for g in gold if leaked(g, cleaned)]
        for attempt in range(4):
            try:
                resp = client.models.generate_content(model=a.model, contents=PROMPTS[a.prompt] + "\n\n---\n" + cleaned)
                answer = resp.text or ""
                break
            except Exception as e:  # quota or transient error: back off and retry within the provider's limits
                answer = f"ERROR {type(e).__name__}: {str(e)[:200]}"
                if "404" in str(e) or "NOT_FOUND" in str(e):
                    raise SystemExit(answer)  # wrong model name: stop, don't count it as a result
                time.sleep(20 * (attempt + 1))
        if answer.startswith("ERROR"):
            print(f"{os.path.basename(path)}: {answer}", flush=True)
            continue
        restored, done, invented = proxy.restore(answer, vault)
        # what is left that still looks like a placeholder after restoring = altered or invented, not restored
        altered = [m.group(0) for m in LOOSE.finditer(restored) if m.group(0) not in invented]
        in_answer = sum(len(re.findall(re.escape(k), answer)) for k in vault)
        row = {"doc": os.path.basename(path), "sent": cleaned, "answer": answer, "restored": restored,
               "issued_kinds_restored": sorted(done), "altered": altered, "invented": invented,
               "payload_leaks": payload_leaks}
        row["in_answer"] = in_answer
        rows.append(row)
        print(f"{row['doc']}: restored {in_answer}, altered {len(altered)}, invented {len(invented)}, "
              f"sent-leaks {len(payload_leaks)}", flush=True)
        time.sleep(4)
    for r in rows:  # re-score every row (older rows too) with the current checks
        r["altered"] = [m.group(0) for m in LOOSE.finditer(r["restored"]) if m.group(0) not in r["invented"]]
        r.setdefault("in_answer", sum(len(re.findall(re.escape(k), r["answer"])) for k in set(PLACEHOLDER_KEYS(r["sent"]))))
    rows.sort(key=lambda r: r["doc"])
    tot = {"issued_in_answer": sum(r["in_answer"] for r in rows), "altered": sum(len(r["altered"]) for r in rows),
           "invented": sum(len(r["invented"]) for r in rows), "payload_leaks": sum(len(r["payload_leaks"]) for r in rows)}
    tot["restored"] = tot["issued_in_answer"]
    summary = {"version": a.version, "prompt": a.prompt, "model": a.model, "docs": len(rows), **tot,
               "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
    json.dump({"summary": summary, "prompt_text": PROMPTS[a.prompt], "rows": rows},
              open(a.log, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
