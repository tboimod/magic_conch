"""Extract the latest COMPLETE mc test rooms block; preserve exact integer counts.

Usage: python tests/aggregate_room_log.py <log.txt> [--out tests/results/room-entry]
Overlapping strata are never added to TOTAL. Old sequence-only logs are rejected.
"""
import argparse
import csv
import json
from pathlib import Path
import re

PREFIX = "[MC ROOM TEST] "
FIELDS = re.compile(r'(\w+)=("(?:\\.|[^"\\])*"|[^ ]+)')


def parse_log(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [i for i, line in enumerate(lines) if any(PREFIX + version in line for version in ("BEGIN v2 ", "BEGIN v3 "))]
    if not starts:
        raise ValueError("No room-entry block. Run the updated `mc test rooms` in Isaac first.")
    start = starts[-1]
    ends = [i for i in range(start, len(lines)) if PREFIX + "END runs=" in lines[i]]
    if not ends:
        raise ValueError("Latest room-entry test is incomplete; partial results are not aggregated.")
    block = [line.split(PREFIX, 1)[1] for line in lines[start:ends[0]+1] if PREFIX in line]
    rows, pairs, phrases = [], [], []
    for line in block:
        fields = dict(FIELDS.findall(line))
        if "counts" in fields:
            counts = [int(value) for value in fields["counts"].split("/")]
            n = int(fields["n"])
            if len(counts) != 3 or sum(counts) != n:
                raise ValueError("Corrupt counts: " + line)
            row = {"section": line.split()[0], **fields}
            for kind, count in zip(("positive", "neutral", "negative"), counts):
                row[kind + "Count"] = count
                row[kind + "Pct"] = 100 * count / n
            rows.append(row)
        elif line.startswith("PAIR "):
            pairs.append(fields)
        elif line.startswith("PHRASE "):
            phrases.append({"section": line.split()[1], **fields})
    totals = [row for row in rows if row["section"] == "TOTAL"]
    methods = {"legacy", "rng_sum", "keyed" if block[0].startswith("BEGIN v3 ") else "rng_mixed"}
    if len(totals) != 3 or {row["method"] for row in totals} != methods:
        raise ValueError("Missing or duplicate TOTAL rows")
    header, ending = dict(FIELDS.findall(block[0])), dict(FIELDS.findall(block[-1]))
    runs = int(header["runs"])
    if any(int(row["n"]) != runs * 169 for row in totals):
        raise ValueError("TOTAL does not match declared run count")
    report = {"source": str(path.resolve()), "header": header, "ending": ending,
        "scope": "synthetic equal-weight slots; actual-floor snapshot is a separate small sample",
        "totals": totals, "pairs": pairs,
        "diagnosticOutliers": [row for row in rows if int(row["n"]) >= 100 and
            (float(row["typeMaxZ"]) > 5 or float(row["textMaxZ"]) > 5)],
        "rows": rows, "phrases": phrases,
        "interpretation": "Strata overlap. Z scores assume IID and are diagnostic only; do not sum strata or treat flags as adjusted hypothesis tests."}
    return report, block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--out", type=Path, default=Path("tests/results/room-entry"))
    args = parser.parse_args()
    try:
        report, block = parse_log(args.log)
    except ValueError as error:
        parser.error(str(error))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "native.log").write_text("\n".join(PREFIX + line for line in block) + "\n", encoding="utf-8")
    columns = sorted({key for row in report["rows"] for key in row})
    with (args.out / "strata.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(report["rows"])
    print(json.dumps({"header": report["header"], "totals": report["totals"], "pairs": report["pairs"]}, ensure_ascii=False, indent=2))
    print(f"Saved {len(report['rows'])} strata; overlapping groups were not pooled: {args.out.resolve()}")


if __name__ == "__main__":
    main()
