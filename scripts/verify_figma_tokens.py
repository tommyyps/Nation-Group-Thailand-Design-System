#!/usr/bin/env python3
"""
ตรวจสอบความสอดคล้องระหว่าง token JSON กับ Figma variable paths

การใช้งาน:
  python3 scripts/verify_figma_tokens.py [--tokens DIR] [--snapshot FILE]

  --snapshot  ไฟล์ JSON ที่มี mapping จาก variableId -> name จาก Figma
              (สร้างได้โดยรัน use_figma / plugin หรือ export จาก Figma)

รูปแบบ snapshot ที่รองรับ:
  { "VariableID:123:456": { "name": "color/base/white-100", ... }, ... }
  หรือ
  { "variables": { "VariableID:...": { "name": "..." } } }

ถ้าไม่ส่ง snapshot สคริปต์จะยังคำนวณ expected Figma path และตรวจสอบว่า
แต่ละ token มี variableId + collection ใน $extensions.figma ตามไฟล์
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

VAR_PREFIX = "VariableID:"


def dot_path_to_figma_path(path: str) -> str:
    """color.text.primary.default -> color/text/primary/default"""
    parts = path.split(".")
    return "/".join(parts)


def expected_figma_path_for_leaf(source_file: str, json_path: str) -> str:
    """สร้าง expected path ให้ตรงกับชื่อตัวแปรจริงใน Figma (snapshot)"""
    exp = dot_path_to_figma_path(json_path)
    if source_file == "primitive.json":
        if json_path.startswith("effect.background-blur."):
            # ตัวแปรเดียวกับ size/blur/* (alias เดียวกันใน Figma)
            tail = "/".join(json_path.split(".")[2:])
            return f"size/blur/{tail}"
    return exp


def walk_tokens(
    obj: Any,
    prefix: str,
    out: list[dict[str, Any]],
    source_file: str,
) -> None:
    if isinstance(obj, dict):
        if "$value" in obj and "$type" in obj:
            ext = obj.get("$extensions", {}).get("figma", {})
            vid = ext.get("variableId")
            coll = ext.get("collection")
            entry = {
                "source": source_file,
                "jsonPath": prefix,
                "expectedFigmaPath": expected_figma_path_for_leaf(source_file, prefix)
                if prefix
                else None,
                "variableId": vid,
                "collection": coll,
                "tokenType": obj.get("$type"),
            }
            out.append(entry)
            return
        for k, v in obj.items():
            if k.startswith("$"):
                continue
            p = f"{prefix}.{k}" if prefix else k
            walk_tokens(v, p, out, source_file)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            walk_tokens(x, f"{prefix}[{i}]", out, source_file)


def load_snapshot(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "variables" in raw:
        raw = raw["variables"]
    out: dict[str, str] = {}
    for k, v in raw.items():
        if not k.startswith(VAR_PREFIX):
            continue
        if isinstance(v, dict) and "name" in v:
            out[k] = v["name"]
        elif isinstance(v, str):
            out[k] = v
    return out


def expected_collection_for_file(name: str) -> str | None:
    if name.startswith("01-primitive"):
        return "VariableCollectionId:4352:8805"
    if name.startswith("02-semantics"):
        return "VariableCollectionId:4355:7291"
    if name.startswith("03-component"):
        return "VariableCollectionId:4355:7289"
    if name == "responsive.json":
        return "VariableCollectionId:8432:4"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify Figma token paths vs JSON")
    ap.add_argument(
        "--tokens",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tokens",
        help="โฟลเดอร์ที่เก็บไฟล์ JSON",
    )
    ap.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="JSON: variableId -> { name } จาก Figma",
    )
    args = ap.parse_args()

    if not args.tokens.is_dir():
        print(f"ไม่พบโฟลเดอร์ tokens: {args.tokens}", file=sys.stderr)
        return 1

    snapshot: dict[str, str] = {}
    if args.snapshot:
        if not args.snapshot.is_file():
            print(f"ไม่พบ snapshot: {args.snapshot}", file=sys.stderr)
            return 1
        snapshot = load_snapshot(args.snapshot)

    json_files = sorted(
        p
        for p in args.tokens.glob("*.json")
        if p.name != "figma-variables.snapshot.json"
        and not p.name.startswith("_")
        and not p.name.endswith(".example.json")
    )
    all_entries: list[dict[str, Any]] = []
    for jp in json_files:
        data = json.loads(jp.read_text(encoding="utf-8"))
        data = {k: v for k, v in data.items() if not k.startswith("$")}
        walk_tokens(data, "", all_entries, jp.name)

    mismatches: list[str] = []
    missing_id: list[str] = []
    wrong_coll: list[str] = []

    for e in all_entries:
        jp = e["jsonPath"]
        if not jp:
            continue
        vid = e.get("variableId")
        exp = e.get("expectedFigmaPath")
        exp_coll = expected_collection_for_file(e["source"])

        if vid and not str(vid).startswith(VAR_PREFIX):
            mismatches.append(f"{e['source']}: {jp} variableId รูปแบบผิด: {vid}")

        if vid and exp_coll and e.get("collection") != exp_coll:
            wrong_coll.append(
                f"{e['source']}: {jp} collection คาดหวัง {exp_coll} ได้ {e.get('collection')}"
            )

        if not vid:
            # typography / effect styles มักใช้ styleId แทน variable
            if e.get("tokenType") == "color" and e["source"].startswith(
                ("01-", "02-", "03-")
            ):
                missing_id.append(f"{e['source']}: {jp} ไม่มี variableId")

        if snapshot and vid and vid in snapshot:
            actual = snapshot[vid]
            if exp and actual != exp:
                mismatches.append(
                    f"{e['source']}: {jp}\n  คาดหวัง Figma: {exp}\n  ได้จาก snapshot: {actual}"
                )  # noqa: PERF401

    print("=== สรุปการตรวจสอบ NTGDS tokens ===\n")
    print(f"ไฟล์ที่อ่าน: {len(json_files)}")
    print(f"จำนวน leaf tokens (มี $value): {len(all_entries)}")
    print(f"มี snapshot สำหรับเทียบชื่อ: {'ใช่' if snapshot else 'ไม่'}\n")

    if missing_id:
        print(f"ไม่มี variableId ({len(missing_id)} รายการ) — ตัวอย่าง:")
        for line in missing_id[:15]:
            print(f"  - {line}")
        if len(missing_id) > 15:
            print(f"  ... และอีก {len(missing_id) - 15} รายการ")
        print()

    if wrong_coll:
        print(f"collection ไม่ตรงกับประเภทไฟล์ ({len(wrong_coll)} รายการ) — ตัวอย่าง:")
        for line in wrong_coll[:10]:
            print(f"  - {line}")
        print()

    if mismatches:
        print(f"ชื่อ path ไม่ตรงกับ snapshot ({len(mismatches)} รายการ):")
        for line in mismatches[:25]:
            print(line)
            print()
        if len(mismatches) > 25:
            print(f"... และอีก {len(mismatches) - 25} รายการ\n")

    if not snapshot:
        print(
            "หมายเหตุ: ส่ง --snapshot ไฟล์ที่มี variableId -> name จาก Figma "
            "เพื่อเทียบชื่อ path แบบเต็มรูปแบบ\n"
            "ตัวอย่างการสร้าง snapshot: รันใน Figma plugin (use_figma) แล้ว export\n"
            "  return Object.fromEntries(vars.map(v => [v.id, { name: v.name }]))\n"
        )

    if wrong_coll or mismatches:
        return 1
    if missing_id:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
