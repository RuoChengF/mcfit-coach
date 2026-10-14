#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
McFit Coach · TOON 营养文本解析器
================================

将麦当劳 MCP `list-nutrition-foods` 返回的非标准 TOON 文本解析为结构化列表。

TOON 原始格式（实测，非 JSON）:
    [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
      猪柳麦满分,null,1288,308,16,16,24,781,213
      芝士安格斯厚牛堡,能量约鲈鱼1条,2914,696,32,44,43,897,150

要点:
  - 首行 `[N]{字段}:` 为表头，N 为条数（仅供参考），{} 内为字段名。
  - 数据行以逗号分隔；第一个字段为 productName，末尾 7 个为数值字段。
  - nutritionDescription 可能为 `null`，也可能含中文描述（甚至逗号，需合并）。
  - energyKcal = 大卡（热量约束用）；sodium / calcium = 毫克(mg)。

用法:
    python3 toon_parser.py [toon_sample.txt]   # 输出 JSON 到 stdout
    python3 toon_parser.py --index [toon_sample.txt]  # 仅输出 {name: item}
"""

import json
import re
import sys

HEADER_RE = re.compile(r"^\[(\d+)\]\{([^}]+)\}\s*:?\s*$")
# 末尾 7 个固定为数值字段
NUMERIC_FIELDS = [
    "energyKj",
    "energyKcal",
    "protein",
    "fat",
    "carbohydrate",
    "sodium",
    "calcium",
]

# ---- 餐品分类启发式（开发期用，最终应以 query-meals 的真实分类为准）----
MAIN_KW = ["堡", "霸", "麦满分", "卷", "粥", "排", "翅", "鱼", "沙拉", "营养卷", "早餐", "鸡块", "鸡球", "鸡腿", "琵琶腿", "里脊"]
SIDE_KW = ["薯条", "玉米杯", "鸡翅", "麦乐鸡", "派", "新地", "麦旋风", "雪冰", "鸡排", "笋卷", "V翅", "油条", "薯饼", "蛋沙拉", "多笋", "趣鸡球", "拉明顿", "冰淇淋", "苹果片"]
DRINK_KW = ["可乐", "雪碧", "咖啡", "茶", "牛奶", "果汁", "苹果汁", "水", "奶铁", "玛奇朵", "卡布奇诺", "怡泉", "橙", "豆浆", "美式", "燕麦", "朱古力", "阿芙佳朵", "悦"]


def parse_toon(text: str) -> list:
    """解析 TOON 文本为结构化餐品列表。"""
    items: list = []
    field_names = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = HEADER_RE.match(line)
        if m:
            field_names = [f.strip() for f in m.group(2).split(",")]
            continue
        if field_names is None:
            continue
        # 跳过疑似重复表头
        if line.startswith("[") and "}" in line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(NUMERIC_FIELDS) + 2:  # 至少 name + desc + 7 数值
            continue
        name = parts[0]
        numeric = parts[-7:]
        desc_parts = parts[1:-7]
        desc = ",".join(desc_parts) if desc_parts else None
        if desc in (None, "null", ""):
            desc = None
        rec = {"productName": name, "nutritionDescription": desc}
        for key, val in zip(NUMERIC_FIELDS, numeric):
            try:
                rec[key] = int(val)
            except (ValueError, TypeError):
                rec[key] = None
        items.append(rec)
    return items


def classify(name: str) -> str:
    """启发式分类：main(主餐) / side(小食) / drink(饮品) / other。"""
    if any(k in name for k in DRINK_KW):
        return "drink"
    if any(k in name for k in SIDE_KW):
        return "side"
    if any(k in name for k in MAIN_KW):
        return "main"
    return "other"


def build_index(items: list) -> dict:
    """名称 -> 餐品（含自动补充的 category 字段）。"""
    idx = {}
    for it in items:
        it = dict(it)
        it.setdefault("category", classify(it["productName"]))
        idx[it["productName"]] = it
    return idx


def main(argv: list) -> int:
    if len(argv) > 1 and argv[1] == "--index":
        path = argv[2] if len(argv) > 2 else None
    else:
        path = argv[1] if len(argv) > 1 else None

    if path:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    items = parse_toon(text)
    if len(argv) > 1 and argv[1] == "--index":
        idx = build_index(items)
        print(json.dumps(idx, ensure_ascii=False, indent=2))
    else:
        out = {"count": len(items), "items": items}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
