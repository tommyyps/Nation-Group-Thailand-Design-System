#!/usr/bin/env python3
"""
แปลงผลลัพธ์ use_figma ที่เป็น JSON { "tsv": "..." } (หรือหลายบรรทัด) เป็น
tokens/figma-variables.snapshot.json

ใช้เมื่อ export แบบแบ่งช่วง (เช่น 200 ตัวแปรต่อครั้ง) เพื่อหลีกเลี่ยงขีดจำกัดความยาวของ MCP

ตัวอย่าง:
  python3 scripts/json_tsv_export_to_snapshot.py tokens/figma-snapshot-tsv/chunk-*.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_tsv_from_json_obj(obj: dict) -> str:
    if "tsv" not in obj:
        raise ValueError("คาดหวังคีย์ 'tsv' ใน JSON")
    tsv = obj["tsv"]
    if not isinstance(tsv, str):
        raise TypeError("tsv ต้องเป็น string")
    return tsv


def main() -> None:
    if len(sys.argv) < 2:
        print("ใช้: json_tsv_export_to_snapshot.py <chunk.json>...", file=sys.stderr)
        sys.exit(1)

    merged: dict[str, dict[str, str]] = {}
    for path_str in sys.argv[1:]:
        p = Path(path_str)
        obj = json.loads(p.read_text(encoding="utf-8"))
        tsv = load_tsv_from_json_obj(obj)
        for line in tsv.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise ValueError(f"{p}: บรรทัดไม่ถูกต้อง: {line[:100]!r}")
            vid, name, cid = parts
            if vid in merged:
                raise SystemExit(f"ซ้ำ variableId: {vid}")
            merged[vid] = {"name": name, "collectionId": cid}

    root = Path(__file__).resolve().parent.parent
    out = root / "tokens" / "figma-variables.snapshot.json"
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"เขียน {len(merged)} ตัวแปร -> {out}")


if __name__ == "__main__":
    main()
