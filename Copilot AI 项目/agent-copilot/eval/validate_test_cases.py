"""
测试用例工具引用健康检查与自动修复。

工具增删后，快速确认测试用例是否需要更新：
  - 已删除的工具 → 自动移除用例中的引用 (--update)
  - 新增的工具    → 报告新增了哪些工具，方便补用例

用法:
  python -m eval.validate_test_cases          # 只检查，报错
  python -m eval.validate_test_cases --update  # 自动移除已删除工具的引用（建议先 git commit 再运行）
"""

import json
import os
import sys


def _get_current_tools():
    """从 MongoDB 获取当前所有 name_for_human。"""
    import mongoengine
    try:
        mongoengine.get_connection()
    except mongoengine.ConnectionFailure:
        mongoengine.connect(db="tools", host="127.0.0.1", port=27112)
    from entity.tool_entity import Tool
    return {t.name_for_human: t.name_for_model for t in Tool.objects()}


def _resolve_path(fp):
    return os.path.join(os.path.dirname(__file__), "test_cases", fp)


def _list_all_tool_refs(fp):
    """遍历 JSON 文件，收集所有工具引用位置。"""
    refs = []  # [(case_index, 字段路径, 值), ...]
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    ARRAY_FIELDS = ["expected_tools", "allowed_tools", "forbidden_tools"]

    for ci, case in enumerate(cases):
        cid = case.get("id", f"#{ci}")
        for field in ARRAY_FIELDS:
            val = case.get(field)
            if val and isinstance(val, list):
                for vi, t in enumerate(val):
                    refs.append((ci, cid, field, vi, t))
        for si, seq in enumerate(case.get("gold_tool_sequence", [])):
            tn = seq.get("tool_name", "")
            if tn:
                refs.append((ci, cid, f"gold_tool_sequence[{si}].tool_name", -1, tn))
    return refs, data, cases


def _remove_orphans(fp, data, cases, orphan_names):
    """从 data 中移除所有指向已删除工具的引用，返回是否修改。"""
    modified = False
    ARRAY_FIELDS = ["expected_tools", "allowed_tools", "forbidden_tools"]
    for ci, case in enumerate(cases):
        for field in ARRAY_FIELDS:
            val = case.get(field)
            if val and isinstance(val, list):
                before = len(val)
                case[field] = [t for t in val if t not in orphan_names]
                if len(case[field]) != before:
                    modified = True
        for si in range(len(case.get("gold_tool_sequence", [])) - 1, -1, -1):
            tn = case["gold_tool_sequence"][si].get("tool_name", "")
            if tn in orphan_names:
                del case["gold_tool_sequence"][si]
                modified = True
    if modified:
        if isinstance(data, dict):
            data["cases"] = cases
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return modified


def main():
    do_update = "--update" in sys.argv
    if do_update:
        print("注意: --update 会修改测试用例 JSON 文件，建议先 git commit 再运行。\n")

    current = _get_current_tools()
    print(f"当前系统工具数: {len(current)}\n")

    cases_dir = os.path.join(os.path.dirname(__file__), "test_cases")
    all_refs = {}  # tool_name → set of (fn, cid, field)
    file_data = {}

    for fn in sorted(os.listdir(cases_dir)):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(cases_dir, fn)
        refs, data, cases = _list_all_tool_refs(fp)
        file_data[fn] = (data, cases, refs)
        for ci, cid, field, vi, t in refs:
            all_refs.setdefault(t, set()).add((fn, cid, field))

    referenced = set(all_refs.keys())
    orphan = referenced - set(current.keys())
    unused = set(current.keys()) - referenced

    # ===== 已删除的工具 =====
    if orphan:
        print("=" * 60)
        print(f"以下 {len(orphan)} 个工具已被删除，但仍有测试用例引用:\n")
        for t in sorted(orphan):
            refs = all_refs[t]
            for fn, cid, field in sorted(refs):
                print(f"  {fn} / {cid}  →  [{field}]")
        print()

        if do_update:
            changed = []
            for fn in sorted(file_data):
                data, cases, refs = file_data[fn]
                if _remove_orphans(os.path.join(cases_dir, fn), data, cases, orphan):
                    changed.append(fn)
            if changed:
                print(f"已自动移除孤儿引用: {', '.join(changed)}")
            else:
                print("无需修改。")
        else:
            print("运行 python -m eval.validate_test_cases --update 可自动移除上述孤儿引用。\n")
    else:
        print("[OK] 所有测试用例的工具引用均存在于当前系统中。\n")

    # ===== 新增的工具 =====
    if unused:
        print("=" * 60)
        print(f"以下 {len(unused)} 个工具存在于系统中但未被任何用例覆盖:\n")
        for t in sorted(unused):
            m = current[t]
            print(f"  {m}  —  {t}")
        print()
        print("可根据需要为这些工具编写新测试用例。")
        print("参考模板:")
        print("""  {
    "id": "tc_single_XXX",
    "query": "...",
    "category": "real_tested",
    "difficulty": "medium",
    "risk_level": "low",
    "expected_tools": ["<工具名称>"],
    "allowed_tools": ["<工具名称>"],
    "success_criteria": {
      "type": "rule",
      "must_have": ["..."],
      "must_not": []
    }
  }""")
        print()

    if not orphan and not unused:
        print("一切正常。")

    summary = []
    if orphan:
        summary.append(f"{len(orphan)} 个删除的工具需处理")
    if unused:
        summary.append(f"{len(unused)} 个新增的工具可补充")
    if summary:
        print("- " + "；".join(summary))


if __name__ == "__main__":
    main()
