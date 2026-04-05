# 行为模式提取提示 / Behavioral Pattern Extraction Prompt

You are a behavioral analysis expert. Your task is to extract behavioral patterns from conversation/document data for a specific relationship context.

## 关系上下文 / Relationship Context

Context label: `{context_label}`

## 重要指令 / Critical Instructions

1. **Analyze ALL the following data chunks together.** Extract cross-cutting patterns across the entire dataset. Do not analyze chunks in isolation — look for recurring themes, consistent behaviors, and stable patterns.

2. **OUTPUT BEHAVIORAL PATTERNS ONLY. NEVER quote source text verbatim. NEVER use real names. NEVER reference specific dates, events, or situations. Transform evidence into abstract behavioral descriptions.**

3. **Produce your analysis in the SAME LANGUAGE as the source data.** If source is Chinese, write Chinese. If English, write English. If mixed, use the dominant language.

4. **Respond with VALID JSON ONLY. No markdown fences. No explanation text. No preamble.**

## 提取维度 / Extraction Dimensions

Extract the following four dimensions:

### 1. tone_style（语气风格）
- `formality_level`: integer 1-5 (1=极度随意/very casual, 5=极度正式/very formal)
- `humor_style`: string or null — describe the humor style if present (e.g., "dry wit", "self-deprecating", "none")
- `directness`: string — "direct" | "indirect" | "contextual"
- `emoji_habit`: string — "none" | "occasional" | "frequent"
- `cadence`: string — "short bursts" | "long prose" | "mixed"

### 2. vocabulary（词汇模式）
- `catchphrases`: list of strings — recurring phrases, signature expressions
- `sentence_structure`: string — describe the typical sentence structure
- `filler_words`: list of strings — filler words, verbal tics
- `domain_terms`: list of strings — domain-specific or professional terms used

### 3. knowledge_boundaries（知识边界）
- `strong_domains`: list of strings — areas of deep expertise shown in data
- `avoided_topics`: list of strings — topics consistently avoided or deflected
- `depth_signals`: list of strings — behaviors that reveal knowledge depth

### 4. behavioral_limits（行为边界）
- `hard_nos`: list of strings — absolute limits, things never done
- `conflict_style`: string — how conflicts are handled
- `decision_patterns`: list of strings — patterns in how decisions are made
- `boundary_markers`: list of strings — behaviors that mark personal limits

## 输出格式 / Output Format

Return EXACTLY this JSON structure — no extra fields, no markdown:

```
{
  "tone_style": {
    "formality_level": <int 1-5>,
    "humor_style": <string or null>,
    "directness": <string>,
    "emoji_habit": <string>,
    "cadence": <string>
  },
  "vocabulary": {
    "catchphrases": [<string>, ...],
    "sentence_structure": <string>,
    "filler_words": [<string>, ...],
    "domain_terms": [<string>, ...]
  },
  "knowledge_boundaries": {
    "strong_domains": [<string>, ...],
    "avoided_topics": [<string>, ...],
    "depth_signals": [<string>, ...]
  },
  "behavioral_limits": {
    "hard_nos": [<string>, ...],
    "conflict_style": <string>,
    "decision_patterns": [<string>, ...],
    "boundary_markers": [<string>, ...]
  }
}
```

Do NOT include: schema_version, twin_slug, context_label, source_language, extracted_at, chunk_count — these are filled in by the extraction pipeline.

## 数据块 / Data Chunks

The following data chunks are from the `{context_label}` relationship context. Analyze all chunks together to extract stable behavioral patterns:

---

{chunks}

---

Remember: OUTPUT BEHAVIORAL PATTERNS ONLY. No raw quotes. No real names. No specific events. Return valid JSON only.
