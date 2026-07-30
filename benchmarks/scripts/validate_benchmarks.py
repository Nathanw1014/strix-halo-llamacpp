#!/usr/bin/env python3
"""Validate every number in BENCHMARKS.md against the raw llama-bench dumps.

Two independent classes of check:

  A. PROVENANCE - does each absolute t/s figure in a table actually appear in some raw
     file under results/, at the SAME metric and the SAME depth? Catches typos, drift
     and figures that were hand-edited into the doc.

  B. ARITHMETIC - are the derived columns (deltas, ratios) consistent with the absolute
     columns in their own row? Fully self-contained; needs no raw file.

Exit status is advisory only; read the report.
"""
import re, os, sys, glob
from collections import defaultdict

ROOT = "/home/alloy/strix-halo-llamacpp/benchmarks"
DOC = os.path.join(ROOT, "BENCHMARKS.md")
RES = os.path.join(ROOT, "results")

# ---------------------------------------------------------------- raw index
ROW = re.compile(r'\|\s*(pp\d+|tg\d+)(?:\s*@\s*d(\d+))?\s*\|\s*([\d.]+)\s*±\s*([\d.]+)\s*\|')

def load_raw():
    """-> {(metric, depth): [(relpath, value, std)]}"""
    idx = defaultdict(list)
    files = 0
    for p in glob.glob(os.path.join(RES, "**", "*"), recursive=True):
        if not os.path.isfile(p):
            continue
        try:
            txt = open(p, errors="ignore").read()
        except Exception:
            continue
        hits = 0
        for line in txt.splitlines():
            m = ROW.search(line)
            if m:
                metric, depth, val, std = m.group(1), int(m.group(2) or 0), float(m.group(3)), float(m.group(4))
                idx[(metric, depth)].append((os.path.relpath(p, RES), val, std))
                hits += 1
        if hits:
            files += 1
    return idx, files

RAW, NFILES = load_raw()

def find(metric, depth, value, tol=0.005):
    """Raw entries matching value at this metric+depth, within tol (relative)."""
    out = []
    for (relpath, v, s) in RAW.get((metric, depth), []):
        if v == value or (value and abs(v - value) / value <= tol):
            out.append((relpath, v, s))
    return out

def find_anywhere(value, tol=0.005):
    """Same value at ANY metric/depth - used to explain a provenance miss."""
    out = []
    for (metric, depth), entries in RAW.items():
        for (relpath, v, s) in entries:
            if v == value or (value and abs(v - value) / value <= tol):
                out.append((relpath, metric, depth, v))
    return out

# ---------------------------------------------------------------- doc tables
def parse_tables(path):
    """-> list of dicts {line, header:[...], rows:[(lineno, [cells])]}"""
    lines = open(path).read().splitlines()
    tables, i = [], 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i+1]):
            hdr = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append((j + 1, [c.strip() for c in lines[j].strip().strip("|").split("|")]))
                j += 1
            tables.append({"line": i + 1, "header": hdr, "rows": rows})
            i = j
        else:
            i += 1
    return tables

def section_of(path, lineno):
    """Nearest preceding ## / ### heading."""
    lines = open(path).read().splitlines()
    for k in range(lineno - 1, -1, -1):
        if lines[k].startswith("#"):
            return lines[k].lstrip("# ").strip()
    return "?"

def num(cell):
    """Absolute value in a cell, or None if it is a %, a ratio, or prose."""
    c = cell.replace("**", "").strip()
    if not c or c in {"--", "-", "—"}:
        return None
    if "%" in c or c.endswith("x"):
        return None
    m = re.fullmatch(r'([\d]+\.?[\d]*)', c)
    return float(m.group(1)) if m else None

def pct(cell):
    m = re.search(r'([+-]?[\d.]+)\s*%', cell.replace("**", ""))
    return float(m.group(1)) if m else None

def ratio(cell):
    m = re.search(r'([\d.]+)\s*x', cell.replace("**", ""))
    return float(m.group(1)) if m else None

# ---------------------------------------------------------------- run checks
tables = parse_tables(DOC)
print(f"# BENCHMARKS.md validation")
print(f"\nIndexed {sum(len(v) for v in RAW.values())} measurements from {NFILES} raw files under results/.")
print(f"Found {len(tables)} markdown tables in the doc.\n")

prov_ok, prov_miss, arith_ok, arith_bad = [], [], [], []

for t in tables:
    hdr = t["header"]
    if not hdr or "depth" not in hdr[0].lower():
        continue
    sec = section_of(DOC, t["line"])
    # metric implied by the section heading
    msec = re.search(r'\b(pp\d+|tg\d+)\b', sec)
    default_metric = msec.group(1) if msec else None

    for lineno, cells in t["rows"]:
        dm = re.search(r'(\d+)', cells[0])
        if not dm:
            continue
        depth = int(dm.group(1))
        for ci, cell in enumerate(cells[1:], 1):
            v = num(cell)
            if v is None or v < 5:      # skip %, ratios, tiny counts
                continue
            colname = hdr[ci] if ci < len(hdr) else f"col{ci}"
            # metric: column name can override the section (e.g. a 'metric' column)
            mcol = re.search(r'\b(pp\d+|tg\d+)\b', colname)
            metric = mcol.group(1) if mcol else default_metric
            if not metric:
                continue
            hits = find(metric, depth, v)
            rec = (lineno, sec, colname, depth, metric, v)
            if hits:
                prov_ok.append(rec + (hits[0][0], len(hits)))
            else:
                prov_miss.append(rec + (find_anywhere(v),))

print("## A. Provenance\n")
print(f"- matched to a raw file: **{len(prov_ok)}**")
print(f"- NOT found in raw data: **{len(prov_miss)}**\n")

if prov_miss:
    print("### Unmatched absolute figures\n")
    print("| doc line | section | column | depth | metric | value | same value elsewhere in raw data |")
    print("|---:|---|---|---:|---|---:|---|")
    for (lineno, sec, col, depth, metric, v, alts) in prov_miss:
        if alts:
            a = "; ".join(f"{f} {mm}@d{dd}" for f, mm, dd, _ in alts[:3])
            if len(alts) > 3:
                a += f" (+{len(alts)-3})"
        else:
            a = "**nowhere**"
        print(f"| {lineno} | {sec[:34]} | {col[:22]} | {depth} | {metric} | {v} | {a} |")
    print()

# ---------------------------------------------------------------- arithmetic
print("## B. Arithmetic of derived columns\n")

def check_pct(lineno, label, got, a, b):
    """got% should equal (b/a - 1)*100"""
    if a in (None, 0) or b is None or got is None:
        return
    want = (b / a - 1) * 100
    # doc rounds to whole percents in most tables; allow the rounding band + slack
    if abs(want - got) <= 1.0:
        arith_ok.append((lineno, label))
    else:
        arith_bad.append((lineno, label, got, round(want, 1), a, b))

def check_ratio(lineno, label, got, a, b):
    if a in (None, 0) or b is None or got is None:
        return
    want = b / a
    if abs(want - got) <= 0.015:
        arith_ok.append((lineno, label))
    else:
        arith_bad.append((lineno, label, got, round(want, 3), a, b))

for t in tables:
    hdr = [h.replace("**", "") for h in t["header"]]
    if not hdr or "depth" not in hdr[0].lower():
        continue
    sec = section_of(DOC, t["line"])
    H = {h.lower(): i for i, h in enumerate(hdr)}

    def col(*names):
        for n in names:
            for h, i in H.items():
                if n in h:
                    return i
        return None

    for lineno, cells in t["rows"]:
        def C(i):
            return num(cells[i]) if i is not None and i < len(cells) else None
        def P(i):
            return pct(cells[i]) if i is not None and i < len(cells) else None
        def R(i):
            return ratio(cells[i]) if i is not None and i < len(cells) else None

        # "Δ q8" = q8 post vs q8 pre ; "Δ q4" = q4 deq-once vs q4 base
        if "δ q8" in H and "q8 pre" in H and "q8 post" in H:
            check_pct(lineno, f"{sec}: Δ q8", P(H["δ q8"]), C(H["q8 pre"]), C(H["q8 post"]))
        if "δ q4" in H and "q4 base" in H and "q4 deq-once" in H:
            check_pct(lineno, f"{sec}: Δ q4", P(H["δ q4"]), C(H["q4 base"]), C(H["q4 deq-once"]))
        if "q8post / f16" in H:
            check_ratio(lineno, f"{sec}: q8post/f16", R(H["q8post / f16"]), C(H["f16"]), C(H["q8 post"]))
        # decode tables
        if "q8 / f16" in H:
            check_ratio(lineno, f"{sec}: q8/f16", R(H["q8 / f16"]), C(H["f16"]), C(H["q8"]))
        if "q4 / f16" in H:
            check_ratio(lineno, f"{sec}: q4/f16", R(H["q4 / f16"]), C(H["f16"]), C(H["q4"]))
        # ceiling tables
        if "mmid adds" in H and "+fa fixes (q4)" in H and "ceil (q4)" in H:
            check_pct(lineno, f"{sec}: mmid adds", P(H["mmid adds"]), C(H["+fa fixes (q4)"]), C(H["ceil (q4)"]))
        if "total vs stock f16" in H and "stock f16" in H and "ceil (q4)" in H:
            c = cells[H["total vs stock f16"]]
            check_pct(lineno, f"{sec}: total vs stock f16", pct(c), C(H["stock f16"]), C(H["ceil (q4)"]))
            if ratio(c) is not None:
                check_ratio(lineno, f"{sec}: total vs stock f16 (x)", ratio(c), C(H["stock f16"]), C(H["ceil (q4)"]))
        # contig table
        if "change" in H and "published f16 (post)" in H and "74434c3 f16 (contig)" in H:
            c = cells[H["change"]]
            check_pct(lineno, f"{sec}: change", pct(c), C(H["published f16 (post)"]), C(H["74434c3 f16 (contig)"]))
            if ratio(c) is not None:
                check_ratio(lineno, f"{sec}: change (x)", ratio(c), C(H["published f16 (post)"]), C(H["74434c3 f16 (contig)"]))
        if "change" in H and "pre-pr master f16" in H and "this stack f16" in H:
            check_pct(lineno, f"{sec}: change", P(H["change"]), C(H["pre-pr master f16"]), C(H["this stack f16"]))
        # 35B ub2048 table
        if "f16 vs stock" in H and "stock master f16" in H and "this stack f16" in H:
            check_ratio(lineno, f"{sec}: f16 vs stock", R(H["f16 vs stock"]), C(H["stock master f16"]), C(H["this stack f16"]))
        # decode CEIL table
        if "ratio" in [h.lower() for h in hdr]:
            idxs = [i for i, h in enumerate(hdr) if h.lower() == "ratio"]
            for i in idxs:
                a, b = C(i - 2), C(i - 1)
                check_ratio(lineno, f"{sec}: ratio(col{i})", R(i), a, b)

print(f"- consistent: **{len(arith_ok)}**")
print(f"- INCONSISTENT: **{len(arith_bad)}**\n")
if arith_bad:
    print("| doc line | derived cell | doc says | data says | from | to |")
    print("|---:|---|---:|---:|---:|---:|")
    for (lineno, label, got, want, a, b) in arith_bad:
        print(f"| {lineno} | {label} | {got} | {want} | {a} | {b} |")
    print()
