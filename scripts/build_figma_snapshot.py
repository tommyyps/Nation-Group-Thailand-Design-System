#!/usr/bin/env python3
"""
รวมไฟล์ TSV (คอลัมน์: variableId, name, collectionId) จาก Figma export
เป็น tokens/figma-variables.snapshot.json สำหรับ verify_figma_tokens.py --snapshot

วางไฟล์ *.tsv ไว้ใน tokens/figma-snapshot-tsv/ แล้วรัน:
  python3 scripts/build_figma_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_tsv(text: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"คาดหวัง 3 คอลัมน์คั่นด้วยแท็บ: {line[:120]!r}")
        vid, name, cid = parts
        out[vid] = {"name": name, "collectionId": cid}
    return out


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    chunks_dir = root / "tokens" / "figma-snapshot-tsv"
    if not chunks_dir.is_dir():
        print(f"ไม่พบโฟลเดอร์: {chunks_dir}", file=sys.stderr)
        sys.exit(1)

    merged: dict[str, dict[str, str]] = {}
    paths = sorted(chunks_dir.glob("*.tsv"))
    if not paths:
        print(f"ไม่พบไฟล์ .tsv ใน {chunks_dir}", file=sys.stderr)
        sys.exit(1)

    for p in paths:
        chunk = parse_tsv(p.read_text(encoding="utf-8"))
        overlap = set(merged) & set(chunk)
        if overlap:
            raise SystemExit(f"คีย์ซ้ำระหว่างไฟล์ ({p.name}): {len(overlap)} รายการ")
        merged.update(chunk)

    out_path = root / "tokens" / "figma-variables.snapshot.json"
    out_path.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"เขียน {len(merged)} ตัวแปร -> {out_path}")


if __name__ == "__main__":
    main()
