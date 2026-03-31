#!/usr/bin/env python3
"""One-off: patch NTGDS token files (effect colors, shadows, typography, blur)."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path("/Users/pitsanuwat_som/Downloads/NTGDS-tokens")

# lineHeight in export was unitless grid (×12px) — convert to explicit px for CSS/DTCG
LINEHEIGHT_TO_PX = {
    6.5: "78px",
    5.5: "66px",
    4.5: "54px",
    3.25: "39px",
    2.75: "33px",
    2.375: "28.5px",
    2.25: "27px",
    2.0: "24px",
    2: "24px",
    1.875: "22.5px",
    1.75: "21px",
    1.625: "19.5px",
    1.5: "18px",
    1.375: "16.5px",
    1.25: "15px",
    1.125: "13.5px",
}

EFFECT_BLOCK = {
    "overlay": {
        "black-5": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [0, 0, 0],
                "alpha": 0.05,
            },
        },
        "black-10": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [0, 0, 0],
                "alpha": 0.1,
            },
        },
    },
    "focus-ring": {
        "brand": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [0.1176, 0.3451, 0.949],
                "alpha": 0.2,
            },
        },
        "neutral": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [71 / 255, 84 / 255, 103 / 255],
                "alpha": 0.1,
            },
        },
        "error": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [217 / 255, 45 / 255, 32 / 255],
                "alpha": 0.2,
            },
        },
        "warning": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [202 / 255, 133 / 255, 4 / 255],
                "alpha": 0.2,
            },
        },
        "success": {
            "$type": "color",
            "$value": {
                "colorSpace": "srgb",
                "components": [3 / 255, 152 / 255, 85 / 255],
                "alpha": 0.2,
            },
        },
    },
}


def patch_primitives(data: dict) -> None:
    if "color" not in data:
        raise SystemExit("Expected top-level color")
    if "effect" in data["color"]:
        del data["color"]["effect"]
    data["color"]["effect"] = EFFECT_BLOCK


def patch_shadows(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    repl = [
        ('"color": "rgba(30, 88, 242, 0.2)"', '"color": "{color.alpha.effect.brand}"'),
        ('"color": "rgba(71, 84, 103, 0.1)"', '"color": "{color.alpha.effect.default}"'),
        ('"color": "rgba(217, 45, 32, 0.2)"', '"color": "{color.alpha.effect.error}"'),
        ('"color": "rgba(202, 133, 4, 0.2)"', '"color": "{color.alpha.effect.warning}"'),
        ('"color": "rgba(3, 152, 85, 0.2)"', '"color": "{color.alpha.effect.success}"'),
        ('"color": "rgba(0, 0, 0, 0.05)"', '"color": "{color.alpha.constant.black-5}"'),
        ('"color": "rgba(0, 0, 0, 0.1)"', '"color": "{color.alpha.constant.black-10}"'),
    ]
    for a, b in repl:
        text = text.replace(a, b)
    path.write_text(text, encoding="utf-8")
    json.loads(text)  # validate


def patch_typography(obj) -> None:
    if isinstance(obj, dict):
        if "lineHeight" in obj and isinstance(obj["lineHeight"], (int, float)):
            key = float(obj["lineHeight"])
            if key in LINEHEIGHT_TO_PX:
                obj["lineHeight"] = LINEHEIGHT_TO_PX[key]
            elif key in (2,):
                obj["lineHeight"] = LINEHEIGHT_TO_PX[2]
        if "styleId" in obj and isinstance(obj["styleId"], str):
            # "S:hex," → "S:hex"
            obj["styleId"] = re.sub(r",\s*$", "", obj["styleId"])
        for v in obj.values():
            patch_typography(v)
    elif isinstance(obj, list):
        for i in obj:
            patch_typography(i)


def patch_background_blur(data: dict) -> None:
    bb = data.get("background-blur")
    if not bb:
        return
    radii = {"xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "40px"}
    for name, dim in radii.items():
        node = bb.get(name)
        if not node:
            continue
        node["$type"] = "dimension"
        node["$value"] = dim
        fig = node.get("$extensions", {}).get("figma")
        if isinstance(fig, dict):
            fig["blurRadius"] = dim
            fig["effectTypes"] = ["BACKGROUND_BLUR"]


def main() -> None:
    prim_path = BASE / "01-primitive.json"
    raw = json.loads(prim_path.read_text(encoding="utf-8"))
    patch_primitives(raw)
    prim_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    patch_shadows(BASE / "shadows.json")

    typ_path = BASE / "typography.json"
    typ = json.loads(typ_path.read_text(encoding="utf-8"))
    patch_typography(typ)
    typ_path.write_text(json.dumps(typ, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sh = json.loads((BASE / "shadows.json").read_text(encoding="utf-8"))
    patch_background_blur(sh)

    def fix_style_ids(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k == "styleId" and isinstance(v, str) and v.endswith(","):
                    o[k] = v[:-1]
                else:
                    fix_style_ids(v)
        elif isinstance(o, list):
            for i in o:
                fix_style_ids(i)

    fix_style_ids(sh)
    (BASE / "shadows.json").write_text(json.dumps(sh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    json.loads((BASE / "shadows.json").read_text(encoding="utf-8"))
    print("OK: patched primitive, shadows, typography")


if __name__ == "__main__":
    main()
