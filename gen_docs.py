"""Synthetic UK-English test documents with known personal data (gold) for the privacy-proxy build.

Every person, number and address here is invented by this script. Numbers carry valid checksums (Luhn cards,
mod-97 IBANs, mod-11 NHS numbers) so a checksum-aware detector cannot cheat. A share of documents gets "noise":
numbers written with dots or spaces, names in lower case, a short form ("Ms Okafor") after the full name, a name
inside an email address, a signature with initials.

    python gen_docs.py --n 60 --seed 20261027 --out testdocs/set1
writes doc_###.txt + doc_###.gold.json (list of {type, value}) per document.
"""
import argparse, json, os, random, string

FIRST = ["Amara", "Tomasz", "Priya", "Callum", "Ngozi", "Eilidh", "Rhys", "Yusuf", "Siobhan", "Mateo", "Hannah",
         "Kwame", "Leila", "Oliver", "Fatima", "Declan", "Mei", "Arjun", "Zofia", "Isaac", "Bronwen", "Tariq",
         "Grace", "Emeka", "Freya", "Dmitri", "Aisha", "Finlay", "Rosa", "Hamish"]
LAST = ["Okafor", "Wiśniewski", "Raman", "McLeod", "Adeyemi", "Fraser", "Pritchard", "Haddad", "Gallagher",
        "Ferreira", "Whitcombe", "Mensah", "Karimi", "Ashworth", "Siddiqui", "Doherty", "Zhang", "Bhatt", "Nowak",
        "Levy", "Price", "Rahman", "Ellison", "Nwosu", "Lindqvist", "Volkov", "Hussain", "Macrae", "Delgado", "Gunn"]
STREETS = ["Linden Grove", "Harbour Row", "Mill Lane", "Ashcombe Road", "Victoria Terrace", "Quarry Close",
           "St Brides Walk", "Kelvin Drive", "Orchard Rise", "Tanners Yard"]
TOWNS = [("Leeds", "LS6"), ("Cardiff", "CF24"), ("Glasgow", "G12"), ("Bristol", "BS3"), ("Norwich", "NR2"),
         ("Belfast", "BT7"), ("Sheffield", "S11"), ("Exeter", "EX4")]
ORGS = ["Harrowgate Dental Practice", "Northfield Lettings Ltd", "Brackenridge Legal LLP", "Calder Valley Surgery",
        "Pennant Logistics Ltd", "Riverside Fostering Trust", "Oakmere Insurance Brokers", "Skelton & Ward Accountants"]
DOMAINS = ["examplemail.co.uk", "mailbox.test", "post.example"]


def luhn_card(rng):
    digits = [4] + [rng.randint(0, 9) for _ in range(14)]
    total = 0
    for i, d in enumerate(reversed(digits)):
        d = d * 2 if i % 2 == 0 else d
        total += d - 9 if d > 9 else d
    return "".join(map(str, digits + [(10 - total % 10) % 10]))


def nhs_number(rng):
    while True:
        d = [rng.randint(0, 9) for _ in range(9)]
        check = 11 - sum(x * w for x, w in zip(d, range(10, 1, -1))) % 11
        check = 0 if check == 11 else check
        if check != 10:
            return "".join(map(str, d + [check]))


def gb_iban(rng):
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    rest = bank + "".join(str(rng.randint(0, 9)) for _ in range(14))
    num = "".join(str(int(c, 36)) for c in rest + "GB00")
    return f"GB{98 - int(num) % 97:02d}{rest}"


def ni_number(rng):
    ok = "ABCEGHJKLMNPRSTWXYZ"
    return rng.choice(ok) + rng.choice(ok.replace("O", "")) + "".join(str(rng.randint(0, 9)) for _ in range(6)) + rng.choice("ABCD")


def phone(rng):
    return "07" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def spaced(value, rng, groups):
    """Write a number in groups with spaces, dots or hyphens (noise)."""
    sep = rng.choice([" ", ".", "-"])
    out, i = [], 0
    for g in groups:
        out.append(value[i:i + g]); i += g
    if i < len(value):
        out.append(value[i:])
    return sep.join(out)


def person(rng, used):
    while True:
        f, l = rng.choice(FIRST), rng.choice(LAST)
        if (f, l) not in used:
            used.add((f, l)); return f, l


TEMPLATES = ["hr", "clinic", "tenancy", "complaint", "invoice"]


def make_doc(rng, noisy):
    used, gold = set(), []
    f1, l1 = person(rng, used); f2, l2 = person(rng, used)
    title1 = rng.choice(["Ms", "Mr", "Dr", "Mrs"])
    town, pc = rng.choice(TOWNS)
    postcode = f"{pc} {rng.randint(1, 9)}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"
    addr = f"{rng.randint(2, 180)} {rng.choice(STREETS)}, {town} {postcode}"
    org = rng.choice(ORGS)
    email = f"{f1.lower()}.{l1.lower().replace('ś', 's')}@{rng.choice(DOMAINS)}"
    tel, card, nhs, iban, ni = phone(rng), luhn_card(rng), nhs_number(rng), gb_iban(rng), ni_number(rng)

    def show(kind, v):
        if not noisy:
            return v
        if kind == "card":
            return spaced(v, rng, [4, 4, 4, 4])
        if kind == "nhs":
            return spaced(v, rng, [3, 3, 4])
        if kind == "iban":
            return spaced(v, rng, [4, 4, 4, 4, 4])
        if kind == "tel":
            return spaced(v, rng, [5, 3, 3])
        return v

    full1, full2 = f"{f1} {l1}", f"{f2} {l2}"
    short1 = f"{title1} {l1}"
    name1_text = full1.lower() if noisy and rng.random() < 0.3 else full1
    kind = rng.choice(TEMPLATES)
    s_tel, s_card, s_nhs, s_iban = show("tel", tel), show("card", card), show("nhs", nhs), show("iban", iban)

    if kind == "hr":
        body = (f"CONFIDENTIAL - {org}\n\nRe: grievance raised by {name1_text} (NI number {ni})\n\n"
                f"{full1} lives at {addr} and can be reached on {s_tel} or {email}. On 3 September {short1} reported "
                f"that her line manager, {full2}, had changed her shifts without notice. {f2} says the rota was agreed "
                f"in August. Salary is paid to account {s_iban}.\n\nPlease prepare a fair written outcome.\n\n"
                f"{f2[0]}. {l2}\nHR Business Partner")
    elif kind == "clinic":
        body = (f"{org}\nReferral letter\n\nPatient: {name1_text}, NHS number {s_nhs}\nAddress: {addr}\n"
                f"Telephone: {s_tel}\n\nDear colleague,\nI saw {short1} today with three weeks of knee pain after a fall. "
                f"{f1} would prefer appointments after 4pm. Next of kin: {full2}.\n\nKind regards,\nDr {l2}")
    elif kind == "tenancy":
        body = (f"{org}\nNotice of rent arrears\n\nTenant: {name1_text}\nProperty: {addr}\n\n"
                f"Dear {short1},\nOur records show two missed payments. The guarantor, {full2}, has been copied in. "
                f"Payments can be made to {s_iban} quoting your reference. If you have questions, email us from "
                f"{email} or call {s_tel}.\n\nYours sincerely,\n{full2[0]}.{l2[0]}. on behalf of {org}")
    elif kind == "complaint":
        body = (f"From: {email}\nTo: complaints@{rng.choice(DOMAINS)}\nSubject: Refund - card ending {card[-4:]}\n\n"
                f"Hello,\nI am {name1_text}. I was charged twice on card {s_card} by {org}. I live at {addr}. "
                f"My partner {full2} witnessed the call. Please phone me on {s_tel}.\n\nThanks,\n{f1}")
    else:
        body = (f"INVOICE 2026-{rng.randint(100, 999)}\n{org}\n\nBill to: {name1_text}\n{addr}\n\n"
                f"Services: consultation and report, GBP {rng.randint(120, 980)}.00\nPay to IBAN {s_iban}\n"
                f"Queries: {full2}, {email}\n\nThank you, {short1}.")

    for t, v in [("name", full1), ("name", full2), ("org", org), ("address", addr), ("email", email)]:
        gold.append({"type": t, "value": v})
    if f1 in body.replace(full1, "").replace(full1.lower(), ""):
        gold.append({"type": "name", "value": f1})
    if f2 in body.replace(full2, ""):
        gold.append({"type": "name", "value": f2})
    if short1 in body:
        gold.append({"type": "name", "value": l1})
    if f"Dr {l2}" in body or f"{f2[0]}. {l2}" in body:
        gold.append({"type": "name", "value": l2})
    for t, raw, shown in [("phone", tel, s_tel), ("card", card, s_card), ("nhs", nhs, s_nhs), ("iban", iban, s_iban),
                          ("ni", ni, ni)]:
        if shown in body:
            gold.append({"type": t, "value": raw, "shown": shown})
    return kind, body, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--noise", type=float, default=0.5, help="share of noisy documents")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    kinds = {}
    for i in range(a.n):
        noisy = rng.random() < a.noise
        kind, body, gold = make_doc(rng, noisy)
        kinds[kind] = kinds.get(kind, 0) + 1
        with open(os.path.join(a.out, f"doc_{i:03d}.txt"), "w", encoding="utf-8") as fh:
            fh.write(body)
        with open(os.path.join(a.out, f"doc_{i:03d}.gold.json"), "w", encoding="utf-8") as fh:
            json.dump({"kind": kind, "noisy": noisy, "gold": gold}, fh, ensure_ascii=False, indent=1)
    print(f"wrote {a.n} documents to {a.out} (seed {a.seed}, noise {a.noise}): {kinds}")


if __name__ == "__main__":
    main()
