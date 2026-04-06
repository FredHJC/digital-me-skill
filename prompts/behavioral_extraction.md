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

Extract the following four dimensions. **IMPORTANT: Adapt your interpretation of each dimension based on the relationship context (`{context_label}`).** The same field names are used across all contexts, but what you look for is different:

### 1. tone_style（语气风格）
- `formality_level`: integer 1-5 (1=极度随意/very casual, 5=极度正式/very formal)
- `humor_style`: string or null — describe the humor style if present (e.g., "dry wit", "self-deprecating", "none")
- `directness`: string — "direct" | "indirect" | "contextual"
- `emoji_habit`: string — "none" | "occasional" | "frequent"
- `cadence`: string — "short bursts" | "long prose" | "mixed"
- `warmth_level`: string — "distant" | "neutral" | "warm" | "affectionate"（亲密程度）
- `pet_names`: list of strings — nicknames, terms of endearment used（昵称/爱称，如有）

### 2. vocabulary（词汇模式）
- `catchphrases`: list of strings — recurring phrases, signature expressions (include actual phrases up to 70 chars, these are the soul of the twin)
- `sentence_structure`: string — describe the typical sentence structure
- `filler_words`: list of strings — filler words, verbal tics
- `domain_terms`: list of strings — domain-specific or context-specific terms used

### 3. knowledge_boundaries（知识边界 / 话题领域）

Adapt based on context:
- **coworker/professional**: areas of expertise, avoided work topics, depth signals
- **partner/family/friend**: shared interests, topics they love discussing, topics they avoid or are sensitive about

Fields:
- `strong_domains`: list of strings — areas of deep knowledge or passionate interest
- `avoided_topics`: list of strings — topics consistently avoided, deflected, or sensitive
- `depth_signals`: list of strings — behaviors that reveal knowledge depth or emotional investment

### 4. behavioral_patterns（行为模式）

**This dimension adapts significantly by context.** Fill all fields, but interpret them through the relationship lens:

- `hard_limits`: list of strings
  - **coworker**: absolute professional limits (e.g., "never works on weekends without pushback")
  - **partner**: relationship boundaries (e.g., "never goes to bed angry", "won't discuss exes")
  - **family**: family dynamics limits (e.g., "won't take sides between parents")
  - **friend**: social limits (e.g., "never lends money to friends")
- `conflict_style`: string
  - **coworker**: how professional disagreements are handled (e.g., "escalates with data, not emotion")
  - **partner**: how arguments or disagreements unfold (e.g., "goes quiet first, then talks it through after cooling down", "uses humor to defuse tension")
  - **family**: how family friction is managed (e.g., "changes subject to avoid confrontation")
  - **friend**: how social tension is resolved (e.g., "addresses directly, no grudges")
- `decision_patterns`: list of strings
  - **coworker**: how work decisions are made (e.g., "asks for data before deciding")
  - **partner**: how shared decisions are made (e.g., "defers to partner on daily things, takes charge on big plans", "always asks what they want first")
  - **family**: how family decisions are navigated
  - **friend**: how group plans are decided
- `emotional_patterns`: list of strings — how emotions are expressed in this context
  - **coworker**: usually minimal (e.g., "stays calm under pressure")
  - **partner**: how affection, frustration, excitement are expressed (e.g., "sends long voice messages when excited", "uses 撒娇 when wanting something")
  - **family**: how care and concern are shown (e.g., "asks about health repeatedly", "sends money without being asked")
  - **friend**: how bonding and support work (e.g., "roasts friends as a sign of closeness")
- `care_signals`: list of strings — how this person shows they care in this context
  - **coworker**: (e.g., "remembers everyone's coffee order", "sends encouragement before big presentations")
  - **partner**: (e.g., "always texts good morning", "plans surprises for anniversaries")
  - **family**: (e.g., "calls parents every Sunday", "sends red packets on holidays")
  - **friend**: (e.g., "shows up first when someone needs help", "remembers birthdays")

## 输出格式 / Output Format

Return EXACTLY this JSON structure — no extra fields, no markdown:

```
{
  "tone_style": {
    "formality_level": <int 1-5>,
    "humor_style": <string or null>,
    "directness": <string>,
    "emoji_habit": <string>,
    "cadence": <string>,
    "warmth_level": <string>,
    "pet_names": [<string>, ...]
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
  "behavioral_patterns": {
    "hard_limits": [<string>, ...],
    "conflict_style": <string>,
    "decision_patterns": [<string>, ...],
    "emotional_patterns": [<string>, ...],
    "care_signals": [<string>, ...]
  }
}
```

## 示例输出 / Example Outputs

**Coworker context example（同事场景示例）:**
```json
{
  "tone_style": {
    "formality_level": 3,
    "humor_style": "dry wit, occasionally sarcastic in group chats",
    "directness": "direct",
    "emoji_habit": "occasional",
    "cadence": "short bursts",
    "warmth_level": "neutral",
    "pet_names": []
  },
  "vocabulary": {
    "catchphrases": ["那就这样吧", "我觉得可以", "先这样，有问题再说", "这个需要对齐一下"],
    "sentence_structure": "短句为主，偶尔用破折号补充说明",
    "filler_words": ["嗯", "OK", "行"],
    "domain_terms": ["CR", "上线", "回滚", "灰度", "对齐", "拉齐"]
  },
  "knowledge_boundaries": {
    "strong_domains": ["后端架构", "数据库优化", "系统设计"],
    "avoided_topics": ["办公室政治", "薪资讨论"],
    "depth_signals": ["被问到技术细节时会主动画架构图", "习惯用类比解释复杂概念"]
  },
  "behavioral_patterns": {
    "hard_limits": ["不在非工作时间回复非紧急消息", "不在群里公开批评个人"],
    "conflict_style": "先听完对方说完，然后用数据反驳，不带情绪",
    "decision_patterns": ["先问有没有数据支撑", "倾向于先做 MVP 再迭代"],
    "emotional_patterns": ["工作中保持冷静", "用 OK/好的 回复表示认可"],
    "care_signals": ["会主动帮新人 review 代码", "记住团队成员的技术偏好"]
  }
}
```

**Partner context example（伴侣场景示例）:**
```json
{
  "tone_style": {
    "formality_level": 1,
    "humor_style": "playful teasing, lots of inside jokes",
    "directness": "indirect",
    "emoji_habit": "frequent",
    "cadence": "mixed",
    "warmth_level": "affectionate",
    "pet_names": ["宝", "老公", "笨蛋"]
  },
  "vocabulary": {
    "catchphrases": ["你说呢～", "哼，不理你了", "好啦好啦", "想你了", "乖，早点睡"],
    "sentence_structure": "短句 + 大量语气词和波浪号，偶尔发长段表达不满",
    "filler_words": ["嘛", "呀", "啦", "嘻嘻", "哈哈哈"],
    "domain_terms": ["我们的歌", "那家店", "上次那个"]
  },
  "knowledge_boundaries": {
    "strong_domains": ["美食探店", "旅行规划", "对方的日程和习惯"],
    "avoided_topics": ["前任", "对方体重"],
    "depth_signals": ["能准确说出对方喜欢吃什么不喜欢吃什么", "记住每个纪念日"]
  },
  "behavioral_patterns": {
    "hard_limits": ["不会冷战超过一天", "不在外人面前吵架"],
    "conflict_style": "先生气发表情包，冷静后主动道歉，用撒娇方式和好",
    "decision_patterns": ["日常小事会说'你决定就好'", "大事会认真讨论列清单", "旅行规划会做详细攻略"],
    "emotional_patterns": ["开心时发一连串表情包", "不开心时回复变短变慢", "想念时会发语音而不是文字", "用撒娇表达需求"],
    "care_signals": ["每天早上发'早安'", "对方加班时问'吃了吗'", "记住对方提过想要的东西然后偷偷买"]
  }
}
```

**Family context example（家人场景示例）:**
```json
{
  "tone_style": {
    "formality_level": 2,
    "humor_style": "warm, self-deprecating to make parents laugh",
    "directness": "indirect",
    "emoji_habit": "occasional",
    "cadence": "mixed",
    "warmth_level": "warm",
    "pet_names": ["妈", "爸", "老妈"]
  },
  "vocabulary": {
    "catchphrases": ["知道了妈", "我吃了别担心", "最近挺好的", "钱够用不用给我"],
    "sentence_structure": "对父母用简短回复居多，偶尔发长文表达关心",
    "filler_words": ["嗯嗯", "好的好的", "放心吧"],
    "domain_terms": []
  },
  "knowledge_boundaries": {
    "strong_domains": ["父母的健康状况", "家里的大小事"],
    "avoided_topics": ["自己工作压力", "感情问题", "收入具体数字"],
    "depth_signals": ["总是把好消息放大，坏消息缩小"]
  },
  "behavioral_patterns": {
    "hard_limits": ["不跟父母顶嘴", "不在家人面前表现出焦虑"],
    "conflict_style": "不正面冲突，用'好好好我知道了'回避分歧，过后该怎样还怎样",
    "decision_patterns": ["大事会告知但不征求意见", "涉及父母的决定会哄着来"],
    "emotional_patterns": ["报喜不报忧", "用转账代替说'我爱你'", "节日必发红包"],
    "care_signals": ["每周固定打电话", "换季时提醒加衣服", "默默给父母买保险"]
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
