#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
McFit Coach · 组合约束求解器
============================

输入营养索引(JSON) 与用户约束，枚举 主餐×小食×饮品 组合，
按 热量上限 / 蛋白下限 / 钠上限 过滤，输出达标 Top-K 方案，
并生成「替换说明」（如 可乐→无糖、薯条→玉米杯 的热量节省）。

用法:
    python3 combo_solver.py --index nutrition_index.sample.json \
        --calorie 600 --protein 40 --sodium 2000 --top 5
"""

import argparse
import json
import sys


def load_index(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    else:
        items = list(data.values())
    idx = {}
    for it in items:
        it = dict(it)
        it.setdefault("category", "other")
        idx[it["productName"]] = it
    return idx


def by_cat(idx: dict, cat: str) -> list:
    return [v for v in idx.values() if v.get("category") == cat]


def total_of(items: list) -> dict:
    t = {"energyKcal": 0, "protein": 0, "sodium": 0, "fat": 0, "carbohydrate": 0}
    for it in items:
        for k in t:
            t[k] += it.get(k) or 0
    return t


def swap_notes(combo: dict, idx: dict) -> list:
    """基于所选方案，生成「换成常规款」可省热量/钠的说明（对标规划书风格）。"""
    notes = []
    drink = combo["drink"]
    side = combo["side"]
    # 饮品: 无糖 -> 常规可乐
    if "无糖" in drink["productName"]:
        reg = next((v for k, v in idx.items() if "可乐" in k and "无糖" not in k), None)
        if reg:
            save = (reg.get("energyKcal") or 0) - (drink.get("energyKcal") or 0)
            notes.append(f"可乐→无糖(-{save}kcal)")
    # 小食: 玉米杯/苹果片 -> 薯条
    if "玉米杯" in side["productName"] or "苹果片" in side["productName"]:
        fries = next((v for k, v in idx.items() if "中薯条" in k), None)
        if fries:
            save = (fries.get("energyKcal") or 0) - (side.get("energyKcal") or 0)
            notes.append(f"薯条→{side['productName']}(-{save}kcal)")
    return notes


def solve(idx: dict, calorie_max: int, protein_min: int, sodium_max: int, top: int, with_side: bool = True) -> list:
    mains = by_cat(idx, "main")
    sides = by_cat(idx, "side") if with_side else [None]
    drinks = by_cat(idx, "drink")
    combos = []
    for m in mains:
        for s in sides:
            for d in drinks:
                parts = [m] + ([s] if s else []) + [d]
                tot = total_of(parts)
                feasible = (
                    tot["energyKcal"] <= calorie_max
                    and tot["protein"] >= protein_min
                    and tot["sodium"] <= sodium_max
                )
                violation = (
                    max(0, tot["energyKcal"] - calorie_max)
                    + max(0, protein_min - tot["protein"]) * 10
                    + max(0, tot["sodium"] - sodium_max) * 0.1
                )
                combo = {
                    "main": m["productName"],
                    "side": s["productName"] if s else None,
                    "drink": d["productName"],
                    "kcal": tot["energyKcal"],
                    "protein": tot["protein"],
                    "sodium": tot["sodium"],
                    "feasible": feasible,
                    "violation": round(violation, 1),
                    "swap_notes": swap_notes({"drink": d, "side": s or {}}, idx) if s else [],
                }
                combos.append(combo)
    # 优先达标方案；无达标则返回最小违规(近似)方案
    feas = [c for c in combos if c["feasible"]]
    pool = feas if feas else combos
    pool.sort(key=lambda c: (not c["feasible"], c["violation"], -c["protein"], c["sodium"], c["kcal"]))
    return pool[:top]


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--calorie", type=int, default=600)
    ap.add_argument("--protein", type=int, default=0)
    ap.add_argument("--sodium", type=int, default=2000)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--no-side", action="store_true")
    args = ap.parse_args(argv[1:])

    idx = load_index(args.index)
    top = solve(idx, args.calorie, args.protein, args.sodium, args.top, with_side=not args.no_side)
    print(json.dumps({"constraints": {"calorie_max": args.calorie, "protein_min": args.protein, "sodium_max": args.sodium}, "count": len(top), "combos": top}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
