import re
import json


class Post:
    @staticmethod
    def extract_pattern(text, pattern):
        # Match ```pattern ...``` allowing optional space after backticks
        regex = re.compile(r"```\s*" + re.escape(pattern) + r"\s(.*?)```", re.DOTALL)
        matches = regex.findall(text)
        if matches:
            return matches[0]

        # Fallback: if no code-fence match, try to extract valid JSON
        if "json" in pattern:
            return _extract_json(text)

        return text


def _clean_json(text: str) -> str:
    """Fix common LLM JSON formatting errors (trailing commas, etc.)."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _extract_json(text: str) -> str:
    """Robust JSON extraction from LLM output that may lack ```json fences.

    Strategy (in order):
      1. Try each '{' as a candidate start — find matching '}', parse, keep
         the longest valid JSON object.
      2. If that fails, try wrapping the longest candidate in an outer {{...}}.
    """
    best = ""
    candidates: list[tuple[int, int]] = []

    # Find all { … } pairs
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for j, c2 in enumerate(text[i:], start=i):
            if c2 == "{":
                depth += 1
            elif c2 == "}":
                depth -= 1
                if depth == 0:
                    candidates.append((i, j + 1))
                    break

    # Try each candidate — keep longest valid JSON (after cleaning)
    for start, end in candidates:
        candidate = _clean_json(text[start:end])
        try:
            json.loads(candidate)
            if len(candidate) > len(best):
                best = candidate
        except json.JSONDecodeError:
            continue

    if best:
        return best

    # Strategy 2: wrap the longest bracket-balanced candidate in {{...}}
    if candidates:
        longest = max(candidates, key=lambda p: p[1] - p[0])
        wrapped = _clean_json("{" + text[longest[0]:longest[1]] + "}")
        try:
            json.loads(wrapped)
            return wrapped
        except json.JSONDecodeError:
            pass

    return text


if __name__ == "__main__":
    text = """```markdown
# 需求清晰度进度条: 60%

## 核心需求理解：
1. **核心目标**: 分析近一周（2025年6月10日-2025年6月17日）台湾媒体及国际舆论对第16届海峡论坛的报道观点，重点关注以下内容
- 台湾参加论坛的“热点人物”在岛内的舆论反应（如政治人物，团体代表）
- 民进党在舆论场中的斗争策略（如抹黑、限制、认知作战等）
- 论坛的潜在风险点（如两岸冲突、政治敏感性等）

2. **需求边界**
- **时间范围**：近一周（2025年6月10日-2025年6月17日）
- **主题范围**：台湾媒体（如TVBS、联合新闻网、中央社）及国际英文媒体（如Reuters、BBC）
- **分析重点**：舆论观点、政党观点、风险研判（非执行落地）。

## 待确认问题：
1. **时间范围**：是否严格限定为“近一周”，或可扩展至论坛前后两周（6月1日-6月17日）？
2. **热点人物**：是否有具体关注对象（如国民党代表团、民间团体领袖）？
3. **国际舆论**：需明确以英文为主，或包含其他语种（如日语、东南亚媒体）？
4. **风险点优先级**：需侧重政治风险、社会反应，还是舆情传播风险？

## 下一步：
请用户确认上述问题，或补充其他需求细节。若需求无调整，请基于当前理解开展分析。

（如需调整关键词或者范围，请直接告知），如需求清晰明了，请回复【需求确认】，我将进行报告生成任务，如果还存在问题，请直接说明。
```
"""
    output = Post.extract_pattern(text, "markdown")
    print(output)