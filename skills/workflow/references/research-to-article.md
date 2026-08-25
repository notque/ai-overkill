---
description: "Multi-agent research pipeline for voice content generation."
user-invocable: false
context: fork
command: /research-article
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - research then write
    - article with research
    - write about
    - research and article
    - full article pipeline
    - comprehensive article
  pairs_with:
    - voice-writer
  complexity: complex
  category: content
---

# Research-to-Article Pipeline

## Overview

This skill orchestrates a complete content pipeline from research to publication. The pipeline operates in six distinct phases, each with defined inputs and gate criteria that must pass before proceeding to the next phase. Each phase produces persistent artifacts (files saved to disk) because context is ephemeral but files remain.

The core principle: research informs the article while the narrative stays in control. Raw data transforms into story before reaching the final output. Always run deterministic validation with `voice-validator.py` at the end because self-assessment is unreliable.

## Instructions

### Phase 1: GATHER (Parallel Research)

**Goal**: Launch parallel research agents to gather comprehensive data on the subject.

**Step 1: Define research scope**

Identify the subject, timeframe, and 6 research dimensions. The current news dimension (Agent 6) is mandatory for profile articles because articles must feel timely — timely journalism captures where the story is RIGHT NOW, not a historical summary from months ago.

```markdown
## Research Scope
Subject: [Person/topic]
Timeframe: [Year or date range]
Agents:
1. [Primary domain] - Core facts, timeline, achievements
2. [Narrative] - Story arcs, character development, turning points
3. [External] - Outside ventures, cross-domain activity
4. [Community] - Fan/audience reaction, social response
5. [Context] - Industry landscape, business implications
6. [Current news] - Last 1-2 weeks: upcoming events, recent developments, announcements
```

Search for these in current news research:
- Upcoming events involving the subject
- Recent developments from the last 2-3 weeks
- Significant changes or announcements
- Media coverage, press conferences, official statements
- Social media announcements or reactions

**Important**: Raw analytics, ratings, or database numbers serve research context only — transform all raw data into narrative for the final article because readers engage with stories, not database numbers like "1771.7 in the ratings and 8.40 community rating". Use data during research to understand trajectory, then express it as narrative in the article: "having the best stretch of their career right now".

**Step 2: Launch 5 parallel agents**

Launch ALL agents in a single message using `Task` with `run_in_background=True`. See `references/research-agents.md` for prompt templates and agent configuration.

**Step 3: Monitor with timeouts**

```
Timeline:
  0:00  - Launch all 5 agents
  2:00  - First progress check (TaskOutput block=false)
  4:00  - Second progress check
  5:00  - HARD TIMEOUT: Proceed with available data
```

Enforce a 5-minute hard timeout on research agents because diminishing returns set in after 3-4 agents provide sufficient data. Waiting indefinitely wastes time without improving quality.

**Gate**: At least 3 of 5 agents have returned data. If fewer than 3, supplement with direct WebSearch. Proceed only when gate passes.

### Phase 2: COMPILE (Structure Research)

**Goal**: Merge agent outputs into a single structured research document with story arc as the primary organizing principle.

**Step 1: Identify the story arc**

Before organizing facts, determine: What is the STORY here? The story arc is the most important element — it frames every fact, quote, and detail. A fact dump (no story arc) becomes a list, not an article. Complete this phase with a clear story arc before moving to GENERATE.

**Step 2: Compile research document**

Structure the compiled document following the template in `references/research-agents.md`:
- Story Arc (1-2 paragraphs — the throughline)
- Key Facts (chronological, with dates and quotes)
- Quotes for Article (direct quotes organized by topic)
- Article Angle (suggested framing + voice notes)

**Step 3: Save research artifact**

```bash
content/[site]/test/[subject]-research.md
```

**Gate**: Research document saved to disk with story arc, key facts, and article angle. Proceed only when gate passes.

### Phase 3: GROUND (Establish Context)

**Goal**: Define the emotional anchor, audience, and voice mode before generation.

Answer these four questions:

| Question | Answer |
|----------|--------|
| What emotion drives this? | [e.g., "comedic irony", "celebration", "redemption"] |
| Who is reading? | [e.g., "community members, enthusiasts"] |
| What voice mode? | [e.g., profile, technical, opinion, tutorial] |
| What is the throughline? | [The single story to tell] |

**Gate**: All four grounding questions answered. Voice and mode selected. Proceed only when gate passes.

### Phase 4: GENERATE (Voice Article)

**Goal**: Generate the article using the appropriate voice skill with research as context.

**Step 1: Load voice skill**

Use the exact `Call the Skill tool with \`skill-name\`.` contract with the indexed `voice-{name}` skill. See `references/voice-variants.md` for voice-specific prompt templates.

**Step 2: Generate with research context**

Key constraints for ALL voices:
- Transform all analytics, ratings, and raw data into narrative — readers want stories, not reports
- Reference the compiled research document by path
- Apply wabi-sabi: natural imperfections are features, not bugs. Do not over-polish
- End with forward momentum — point ahead, not backward. Voice-authentic writing never summarizes. Summary paragraphs are an AI tell

**Step 3: Save draft**

```bash
content/[site]/test/[subject]-article.md
```

**Gate**: Draft article saved to disk. Proceed only when gate passes.

### Phase 5: VALIDATE

**Goal**: Run deterministic validation and refine if needed.

**Step 1: Run validator**

```bash
python3 $HOME/vexjoy-agent/scripts/voice-validator.py validate \
  --content /path/to/article-draft.md \
  --profile $HOME/vexjoy-agent/skills/voice-[name]/profile.json \
  --voice [name] \
  --format json
```

Run `voice-validator.py` every time because self-assessment is unreliable — validation is mandatory, not optional.

**Step 2: Check pass criteria**

| Metric | Requirement |
|--------|-------------|
| Score | >= 60 |
| Errors | 0 |
| Warnings | <= 5 |

**Step 3: Refine if needed**

If validation fails:
1. Address errors first (banned patterns, em-dashes)
2. Address warnings (rhythm, metrics)
3. Re-validate
4. Maximum 3 iterations — if still failing after 3, output with validation report and note issues

Common fixes:
- Check for research language ("metrics show", "data indicates") and replace with narrative
- Check for banned patterns and remove
- Re-read voice profile and adjust tone

**Gate**: Validation passes OR 3 refinement iterations exhausted. Proceed only when gate passes.

### Phase 6: OUTPUT

**Goal**: Deliver final article with validation report and saved artifacts.

**Step 1: Present final output**

```
========================================
 ARTICLE: [Title]
========================================

[Full article content]

========================================
 VALIDATION REPORT
========================================

 Status: PASSED/FAILED
 Score: [X]/100
 Iterations: [N]

 Research: [path to research doc]
 Article: [path to article]

========================================
```

**Step 2: Verify artifacts exist**

Confirm both files are saved — this is non-optional verification because files persist when context vanishes:
- Research document at `content/[site]/test/[subject]-research.md`
- Article at `content/[site]/test/[subject]-article.md`

**Gate**: Final output presented with validation report. Both artifacts confirmed on disk. Pipeline complete.

---

## Examples

### Example 1: Full Article Pipeline
User says: "Write an article about [subject]'s 2025"
Actions:
1. Launch 5 parallel research agents on [subject] 2025 (GATHER)
2. Compile findings into story arc (COMPILE)
3. Ground: celebration, community, profile mode (GROUND)
4. Generate with appropriate voice skill, research as context (GENERATE)
5. Validate with voice-validator.py, score 97/100 (VALIDATE)
6. Output article with validation report, both files saved (OUTPUT)
Result: Published-quality article with deterministic validation

### Example 2: Research with Existing Data
User says: "Write article using this research I already have"
Actions:
1. Skip GATHER phase, load provided research (--skip-research)
2. Verify research has story arc, compile if needed (COMPILE)
3. Ground voice and mode based on content type (GROUND)
4. Generate article from provided research (GENERATE)
5. Validate and refine (VALIDATE)
6. Output with report (OUTPUT)
Result: Article from pre-gathered research, still validated

---

## Error Handling

### Error: "Research Agents Timeout After 5 Minutes"
Cause: Agents stuck on paywalled sites, rate-limited APIs, or unresponsive sources
Solution:
1. Proceed with data from agents that completed (graceful degradation)
2. Supplement gaps with direct WebSearch on specific questions
3. Note missing dimensions in compiled research
4. Article quality is still achievable — sufficient research > comprehensive research

### Error: "Validation Score Below 60"
Cause: Voice drift, research language leaking into article, or banned patterns present
Solution:
1. Check for research language ("metrics show", "data indicates") and replace with narrative
2. Check for banned patterns (em-dashes, corporate jargon) and remove
3. Re-read voice profile and adjust tone
4. Maximum 3 refinement iterations before outputting with warning

### Error: "Voice Skill Not Found"
Cause: Requested voice skill does not exist or has wrong path
Solution:
1. List available voice skills with `ls skills/voice-*/SKILL.md`
2. Verify skill name matches exactly (e.g., `voice-yourname` not `voice-your`)
3. Fall back to `voice-writer` which handles voice selection internally

### Error: "Research Document Missing Story Arc"
Cause: Agents returned facts without narrative structure
Solution:
1. Re-read all agent outputs and identify the connecting thread
2. Write story arc manually based on compiled facts
3. Story arc must answer: "What is the STORY of this subject's [timeframe]?"
4. Do not proceed to GENERATE without a clear story arc

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/research-agents.md`: Agent configuration, prompts, and timeout management
- `${CLAUDE_SKILL_DIR}/references/voice-variants.md`: Voice-specific templates, CLI usage, and proven examples

### Integration

| Skill | Integration |
|-------|-------------|
| `voice-writer` | Used for Phase 4 voice generation |
| `voice-{name}` | Loaded for target voice content |
| `publish` | Upload final article (post-pipeline) |
