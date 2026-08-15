---
description: "Analyze writing samples and extract voice patterns for profiles."
user-invocable: false
command: /voice
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
    - voice calibrate
    - calibrate voice
    - voice profile
    - voice analysis
    - voice refine
  pairs_with:
    - voice-writer
    - voice-validator
  complexity: Medium
  category: content
---

# Voice Calibrator

## Overview

This pipeline analyzes writing samples and generates voice skill files for deterministic content generation. Each voice gets its own skill in `skills/voice-{name}/` with both AI instructions (SKILL.md) and machine-readable metrics (profile.json).

**Architecture**: Sample-first generation with prompt engineering best practices for maximum voice fidelity.

**Core principle**: The quantity and organization of writing examples matters more than rules. LLMs are pattern matchers—samples show HOW the voice sounds; rules tell WHAT it should be. Samples are more powerful.

---

## Instructions

### Mode 1: Full Calibration (ANALYZE-GENERATE-VALIDATE)

Use when: First calibration or major style update

#### Step 1: COLLECT Samples (EXTENSIVE COLLECTION REQUIRED)

You need 50-100+ writing samples for authorship matching to work.

Historical lesson: V7-V9 failed with 3-10 samples. V10 passed with 100+ samples because it had extensive categorized sample collections, not just rules. The samples ARE the skill. Rules are secondary.

Sources to mine:
- Reddit comment history (most valuable - casual voice)
- HackerNews comments
- Forum posts
- Blog posts
- Email threads (if provided)
- Chat logs (if provided)

Required minimum:
- 50+ individual samples
- Mix of response lengths (short, medium, long)
- Mix of contexts (technical, casual, disagreement)

Save samples to: `skills/voice-{name}/references/samples/`

Organize by source:
  - `reddit-samples-YYYY-MM-DD.md`
  - `hn-samples-YYYY-MM-DD.md`
  - `blog-samples.md`

Command:
```bash
mkdir -p skills/voice-{name}/references/samples
```

**Gate**: If user only provides 3-5 samples, STOP. Ask for more. Explain that authorship matching requires 50+ samples. Suggest: "Can you export your Reddit/HN comment history?"

#### Step 2: ANALYZE (Deterministic)

Run voice analyzer on samples to extract quantitative metrics:

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json

# View text report for interpretation
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --format text
```

The script extracts:
- Sentence length distribution (short/medium/long/very long percentages)
- Punctuation metrics (comma density, em-dash count, question rate)
- Word metrics (contraction rate, person usage, function word signature)
- Structure metrics (paragraph length, fragment rate, sentence starters)
- Pattern signatures (transitions used/avoided, opening/closing patterns)

**Reasoning**: Quantitative grounding prevents vague interpretations. Metrics like "contraction rate: 85%" or "avg sentence length: 14.2 words" are specific and measurable, not subjective descriptions.

#### Step 3: GENERATE (AI)

Using profile.json as foundation, generate three artifacts:

**3a. config.json** - Validation settings

This defines how strictly to validate content against the profile:
- `metric_tolerance`: How strict (0.2 = ±20% variance allowed)
- `required_checks`: Must-pass validations (banned_phrases, punctuation, rhythm)
- `optional_checks`: Nice-to-have validations (metrics, sentence_starters)
- `voice_specific_patterns`: Custom rules for this voice

Example template:
```json
{
  "name": "{Voice Name}",
  "version": "2.0.0",
  "description": "{Voice description}",
  "modes": ["chat", "blog", "technical"],
  "validation": {
    "strict_banned_patterns": true,
    "em_dash_forbidden": true,
    "metric_tolerance": 0.20,
    "required_checks": ["banned_phrases", "punctuation", "rhythm"],
    "optional_checks": ["metrics", "sentence_starters"]
  }
}
```

**3b. SKILL.md** - AI instructions with EXTENSIVE SAMPLE SECTIONS

**CRITICAL**: The SKILL.md must be LONG (2000+ lines minimum).

Most of the file should be SAMPLES, not rules. This is the inverse of typical prompt engineering—examples are more powerful than abstract instructions.

Required sections in order of importance:

**a. Phase 1: Voice Grounding (Read Before Writing)** (~400+ lines)

Real samples organized by response length and pattern. This section should be the LONGEST section in the skill:
- 10+ samples each for short/medium/long responses
- 5+ samples each for key patterns: mistakes, limits, disagreement, technical explanation

Structure:
```markdown
## Phase 1: Voice Grounding (Read Before Writing)

Read these actual samples to internalize the voice:

### Sample A: Short Response
> [Actual sample text]

### Sample B: Technical Explanation
> [Another sample]

### Sample C: Admitting Limits
> [Sample showing vulnerability]
```

Reason for front-loading samples: Roasters detect when content captures IDEAS but not EXECUTION STYLE. Execution style comes from extensive example exposure, not rule following.

**b. Phrase Fingerprints** (~50 lines)

10+ distinctive phrase patterns with exact quotes. These are what roasters use to match authorship:
- Recurring sentence starters
- Characteristic closers
- Unique idioms or expressions
- Verbal tics

**c. Natural Typos** (~20 lines)

5+ real typos from their writing. Authenticity markers that humans have but AI typically doesn't.

**d. Voice Metrics** (~100 lines)

Quantitative targets extracted from profile.json:
- Sentence length targets and ranges
- Contraction rate percentage
- Em-dash usage (if any)
- Paragraph length patterns
- Fragment rate

**e. Human Authenticity Markers** (~300 lines)

Teach these 16 patterns explicitly—they distinguish human writing from AI-generated content. Generated content will fail authenticity checks without them:

1. **Incomplete work admissions** - Include at least one admission of something incomplete, imperfect, or "inelegant" (e.g., "I haven't yet built the X feature")
2. **Tangential tool/process references** - Allow tangents showing actual workflow (e.g., "I built a custom tool for that")
3. **Assumed shared context** - Parenthetical winks assuming reader knowledge (e.g., "(that Rob Pike)")
4. **Evolution/iteration narrative** - Show history of attempts, not just final solution (e.g., "The first was X, but that missed Y")
5. **Mid-thought discoveries** - Include moments where learning happens during writing (e.g., "new to me, suggested by Claude")
6. **Unhedged strong opinions** - State opinions directly with full conviction (e.g., "I think this is wrong" rather than "One might argue")
7. **Playful/subversive notes** - Allow personality to bleed through in unexpected moments
8. **Specific artifacts** - Reference real, specific things that can be verified (actual commits, real commands, specific dependencies)
9. **Visible self-correction** - Show thinking that changes direction mid-paragraph (e.g., "At first I thought... but then I realized")
10. **Raw emotion/profanity** - When quoting others' strong reactions, preserve them raw
11. **Exploration admission** - Admit when exploration yielded nothing valuable (e.g., "nothing of real value came about from")
12. **Soft future planning** - Plans should have uncertainty built in (e.g., "likely tomorrow but we will see")
13. **Metaphor as framing device** - Use metaphors to frame ideas, not explain them
14. **Not-X-but-Y lists** - When listing alternatives, use contrast pair format for technical specs
15. **Hypothesis-experiment framing** - Frame investigations as experiments with explicit uncertainty
16. **Casual closers/interjections** - End thoughts with casual, almost throwaway observations

**f. Anti-Essay Patterns** (~150 lines)

Patterns that AI frequently uses but humans rarely do—these kill authenticity matching:

- "It's not X. It's Y" rhetorical pivots (distinct from technical "Not X: Y" contrast pairs)
- "Raises important concerns about..." hedging language
- "One might argue..." passive formality
- "It's worth noting that..." editorial flourish
- Exhaustive explanations and over-completeness
- Wall-of-text paragraphs without natural breaks
- Perfectly resolved tension/conflict
- Prescriptive advice without caveats

**g. Rules and Prohibitions** (~200 lines)

- Banned phrases specific to this voice
- Em-dash rules (forbidden for most voices)
- Contraction minimums/maximums
- Paragraph structure constraints
- Sentence starter preferences/prohibitions

**h. Generation Protocol** (~100 lines)

Pre/During/Post checklists:
- Before writing: What patterns apply to this topic?
- During writing: Check sentence lengths, contraction rate, paragraph breaks
- After writing: Run authenticity markers checklist

**SKILL.md needs 1500+ lines to have enough samples for reliable voice matching.**

Reasoning: The file length correlates with sample collection depth. A short file signals insufficient grounding.

#### Step 4: VALIDATE (Deterministic)

Generate test content using the voice skill, then validate against profile:

```bash
# Generate test content (AI), save to temp file
# Then validate against profile

python3 ~/.claude/scripts/voice-validator.py validate \
  --content test-output.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

Exit codes:
- 0 = pass (score >= 70)
- 1 = fail (score < 70)
- 2 = execution error

**Interpretation**: If validation fails:
1. Show violations (errors, warnings, info)
2. Adjust SKILL.md guidance based on violations
3. Regenerate test content and revalidate (max 3 iterations)

The reason we iterate: Validation can surface issues in the SKILL.md instructions that AI misinterpreted. Each iteration helps sharpen the rules.

#### Step 5: OUTPUT

Display calibration summary:

```
===============================================================
 VOICE CALIBRATION COMPLETE
===============================================================

 Voice: {name}
 Samples: {N} files analyzed

 Generated Files:
   [check] skills/voice-{name}/profile.json    (metrics)
   [check] skills/voice-{name}/config.json     (settings)
   [check] skills/voice-{name}/SKILL.md        (AI instructions)
   [check] skills/voice-{name}/references/samples/  (copied samples)

 Validation: PASSED (score: {score}/100)

 Key Metrics (from profile.json):
   Avg sentence length: {X} words
   Contraction rate: {X}%
   Em-dash usage: {em_dash_count} (target: 0 for most voices)
   Short sentences: {X}%
   Fragment rate: {X}%

===============================================================
```

**Gate**: All 4 generated files exist (profile.json, config.json, SKILL.md, samples/). Validation score >= 70. A/B comparison shows measurable voice differentiation.

---

### Mode 2: Refinement

Use when: Adjusting specific parameters based on feedback

Supported adjustments:
- "Make sentences shorter" → Reduce avg length target by 20%
- "Use fewer lists" → Set list_usage to "rare"
- "More direct openings" → Increase direct_statement percentage
- "Less formal" → Adjust formality marker

Process:
1. Load existing profile.json
2. Apply adjustment to relevant metric
3. Update config.json thresholds if needed
4. Regenerate SKILL.md sections
5. Validate with check-banned for quick feedback

Quick validation:
```bash
python3 ~/.claude/scripts/voice-validator.py check-banned \
  --content test-output.md \
  --voice {name} \
  --format text
```

**Gate**: Adjusted metrics saved to profile.json. `check-banned` passes on test output. SKILL.md sections updated to reflect metric changes.

---

### Mode 3: A/B Comparison Only

Use when: Testing calibration on new topic

Process:
1. Read existing profile.json
2. Take topic from user
3. Generate DEFAULT output (generic Claude style)
4. Generate CALIBRATED output (apply SKILL.md)
5. Validate CALIBRATED output:
   ```bash
   python3 ~/.claude/scripts/voice-validator.py validate \
     --content calibrated-output.md \
     --profile skills/voice-{name}/profile.json \
     --format text
   ```
6. Highlight specific differences

**Gate**: Both DEFAULT and CALIBRATED outputs generated. Validation passes on calibrated output. Specific differences highlighted for user review.

---

### Mode 4: Voice Comparison

Use when: Comparing two calibrated voices

```bash
python3 ~/.claude/scripts/voice-analyzer.py compare \
  --profile1 skills/voice-profile-a/profile.json \
  --profile2 skills/voice-profile-b/profile.json \
  --format text
```

Shows differences in:
- Sentence metrics (average length, variance, distribution)
- Punctuation metrics (comma density, em-dash usage)
- Word metrics (contraction rate, person usage)
- Pattern signatures (unique transitions, opening/closing patterns)

**Reasoning for comparison**: Understanding how two voices differ at the metric level helps calibrate which samples most strongly drive the differences.

---

## Prompt Engineering Best Practices for Voice Skills

When generating voice skills, apply these techniques for maximum effectiveness:

### 1. Attention Anchoring (Bolding)

Apply **bold** to critical constraints and safety guardrails:

```markdown
**Use direct phrasing** instead of the "It's not X. It's Y" rhetorical pattern.
**Replace all em-dashes** with colons, commas, or periods.
```

**Mechanism**: Acts as attention flag for tokenizer, increasing statistical weight of constraint.

### 2. Cognitive Chunking (Headers)

Enforce clear hierarchy of instruction. Never present as wall of text:

```markdown
## Identity (Who the voice is)
## Core Directives (What the voice does)
## Style & Tone (How the voice speaks)
## Negative Constraints (What to avoid)
```

**Mechanism**: Helps model separate distinct logical tasks, reducing "instruction bleeding."

### 3. Context Isolation (Delimiters)

Separate static instructions from dynamic context using horizontal rules and XML tags:

```markdown
---
(Use horizontal rules between sections)

<context>
(Use XML tags for user-provided content)
</context>
```

**Mechanism**: Prevents model from confusing user input with system rules.

### 4. Probability Dampening (Adverbs)

Use adverbs when defining personality/tone. Prefer graduated instructions over absolute binaries:

```markdown
Write in a **subtly** skeptical tone.
Be **generally** direct rather than absolutely blunt.
Sound **slightly** informal while maintaining clarity.
```

**Mechanism**: Restricts token probability distribution less aggressively, preventing caricature.

### 5. Chain-of-Thought Triggers

For complex voice generation, add explicit logic directives:

```markdown
Before writing, think step-by-step:
1. What is my actual position on this topic?
2. What would I say if asked about this in a forum?
3. What process did I go through to form this opinion?
```

**Mechanism**: Forces intermediate token generation, increasing accuracy.

### 6. Few-Shot Examples (Pattern Matching)

Include 1-3 examples of ideal interaction at end of skill:

```markdown
User: "Explain why caching is hard"
Model (WRONG): "Caching is not storage. It's a bet about the future."
Model (CORRECT): "Think of caching as a bet about the future, not persistent storage."
```

**Mechanism**: LLMs are pattern matchers. Examples are more powerful than instructions.

### 7. Sample-First Architecture

Present actual writing samples BEFORE rules:

```markdown
## Phase 1: Voice Grounding (Read Before Writing)

Read these actual samples to internalize the voice:

### Sample A: Technical Explanation
> [Actual sample text from user's writing]

### Sample B: Personal Opinion
> [Another sample showing different context]
```

**Mechanism**: Samples show HOW the voice sounds. Rules tell WHAT it should be. Samples are more effective.

---

## Authenticity Checklist for Generated Skills

Before finalizing any voice skill, verify it teaches these patterns:

**Core 10 (Required):**
- [ ] Incomplete work admissions (teaches vulnerability)
- [ ] Tool/process tangents (teaches showing work)
- [ ] Parenthetical asides (teaches assumed context)
- [ ] Evolution narrative (teaches iteration visibility)
- [ ] Mid-thought discoveries (teaches learning in public)
- [ ] Unhedged opinions (teaches assertion over hedging)
- [ ] Playful moments (teaches personality)
- [ ] Specific artifacts (teaches concreteness)
- [ ] Visible self-correction (teaches thinking out loud)
- [ ] Raw emotion preservation (when quoting)

**Extended 6 (From calibration samples):**
- [ ] Exploration admission (admits dead ends)
- [ ] Soft future planning (hedged schedules)
- [ ] Metaphor as framing device
- [ ] Not-X-but-Y lists (contrast pairs for specs)
- [ ] Hypothesis-experiment framing
- [ ] Casual closers/interjections

---

## Anti-Essay Patterns (CRITICAL FOR AUTHORSHIP MATCHING)

These patterns are red flags that signal AI-generated content and kill authenticity matching:

### Pattern 1: "It's not X. It's Y" Rhetorical Pivots

**Bad**:
> "It's not a caching problem. It's a consistency problem."

**Why harmful**: This rhetorical pattern is nearly universally used by AI. Humans rarely frame in this exact structure.

**Alternative for humans**:
> "The real issue is consistency, not caching."

**Note**: This is DIFFERENT from technical "Not X: Y" contrast pairs (e.g., "Not kubectl get logs: a crashloop-investigator skill"), which are acceptable for specification.

### Pattern 2: Hedging Language

**Bad**:
- "This raises important concerns about..."
- "One might argue that..."
- "It's worth noting that..."
- "It could be said that..."

**Why harmful**: AI defaults to hedging for safety. Humans assert directly.

**Alternative for humans**:
- "I think this is wrong because..."
- "The real problem is..."
- "Here's what I'd do..."

### Pattern 3: Exhaustive Explanations

**Bad**:
> "There are several approaches one could take. First, you could try X. However, X has limitations. Second, you could try Y. This approach has benefits but also drawbacks. Finally, Z is another option. To summarize, each has tradeoffs..."

**Why harmful**: Exhaustive coverage is AI's default. Humans jump to what they use and mention others in passing.

**Alternative for humans**:
> "I use X for this. Some people prefer Y, but I find X works better."

### Pattern 4: Perfect Resolution

**Bad**:
> "After struggling with this for weeks, I finally realized the core issue was..."

**Why harmful**: Too clean. Humans often leave problems partially resolved.

**Alternative for humans**:
> "I still haven't fully solved this, but I think the issue might be..."

### Pattern 5: Wall-of-Text Paragraphs

**Bad**:
Single paragraph with 5+ sentences, no natural breaks.

**Why harmful**: Breaks come from natural breathing points in human thinking, not just paragraph topic.

**Alternative**: Use 2-3 sentence paragraphs, breaks where you naturally pause.

### Pattern 6: Prescriptive Advice Without Caveats

**Bad**:
> "You should always validate input before processing."

**Why harmful**: AI gives absolute rules. Humans qualify.

**Alternative**:
> "I always validate input first, though sometimes you can skip it if you're confident about the source."

---

## Anti-Essay Checklist for Generated Skills

Before finalizing, scan SKILL.md and generated samples for these anti-patterns. If found, flag for revision:

- [ ] "It's not X. It's Y" pivots (rhetorical structure, NOT technical contrast)
- [ ] Hedging language (raises concerns, one might argue, worth noting)
- [ ] Exhaustive option lists (first... second... finally...)
- [ ] Perfect narrative resolution
- [ ] Wall-of-text paragraphs
- [ ] Prescriptive absolutes without hedges
- [ ] Over-explanation and over-completeness
- [ ] Editorial flourishes ("As a matter of fact")
- [ ] Sanitized emotion (softened quotes)
- [ ] Passive voice in personal narrative

---

## Deterministic Infrastructure

Two required scripts power deterministic analysis:

### voice-analyzer.py

Extracts quantitative metrics from writing samples:

```bash
python3 ~/.claude/scripts/voice-analyzer.py analyze \
  --samples skills/voice-{name}/references/samples/*.md \
  --output skills/voice-{name}/profile.json
```

Produces profile.json with:
- Sentence length distribution (min, mean, max, percentiles)
- Punctuation metrics (comma density, em-dash frequency, question rate)
- Word metrics (contraction rate, person usage, function word signature)
- Structure metrics (paragraph length, fragment rate, sentence starters)
- Pattern signatures (transitions, opening/closing patterns)

### voice-validator.py

Validates generated content against profile:

```bash
python3 ~/.claude/scripts/voice-validator.py validate \
  --content test-output.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text
```

Produces violations report with:
- Banned phrase violations
- Metric tolerance violations
- Rhythm/structure violations
- Authenticity pattern gaps

---

## Multi-Voice Support

Organize multiple voices at: `skills/voice-{name}/`

Each voice directory structure:
```
skills/voice-{name}/
  ├── SKILL.md                (AI instructions)
  ├── profile.json            (statistical metrics)
  ├── config.json             (validation settings)
  └── references/
      └── samples/            (raw writing samples)
```

Commands to manage:
```bash
# List all voices
/voice list

# Show specific voice profile
/voice show --name {name}

# Compare two voices
python3 ~/.claude/scripts/voice-analyzer.py compare \
  --profile1 skills/voice-a/profile.json \
  --profile2 skills/voice-b/profile.json
```

---

## Error Handling

### Error: "Insufficient samples"

Minimum 3 samples required. If fewer provided:
1. List available posts in content/posts/
2. Suggest using batch mode to analyze all
3. Request additional samples

**Reasoning**: Statistical significance requires minimum data. 50+ samples is the practical target for authorship matching to work.

### Error: "Samples too similar"

All samples from same time period or topic:
1. Note potential bias in profile
2. Recommend diverse sample selection
3. Proceed with warning in profile

**Reasoning**: Homogeneous samples may miss variation in voice across contexts.

### Error: "No existing profile for comparison"

When A/B mode requested without prior calibration:
1. Run full calibration first
2. Or use DEFAULT voice as baseline

### Error: "Validation failed after 3 iterations"

When content repeatedly fails validation:
1. Check if profile metrics are achievable
2. Review banned patterns for false positives
3. Consider relaxing metric_tolerance in config.json
4. Manual review of SKILL.md instructions

**Reasoning**: Iteration limit prevents infinite loops. If 3 passes still leave failures, the profile may be over-constrained or SKILL.md instructions may be contradictory.

### Error: "Script execution failed"

Check:
1. Python 3 available
2. Scripts executable
3. File paths valid

```bash
python3 ~/.claude/scripts/voice-analyzer.py --help
python3 ~/.claude/scripts/voice-validator.py --help
```

---

## References

- `scripts/voice-analyzer.py`: Deterministic metrics extraction
- `scripts/voice-validator.py`: Content validation against profile
- `scripts/data/banned-patterns.json`: Shared banned pattern database

## Reference Implementations

Create your own voice skill using the voice-calibrator workflow. A complete voice skill includes:
- A SKILL.md with voice patterns, anti-patterns, and validation rules
- A profile.json with statistical voice metrics
- Sample files organized by writing context (forums, blogs, comments)

**Study `skills/workflow/references/voice-calibrator.md` to understand the calibration process.**

---

## Quick Reference Card

| Command | Action |
|---------|--------|
| `/voice calibrate --name [name] --samples [files]` | Create new voice with deterministic analysis |
| `/voice refine --name [name] --samples [files]` | Update voice with additional samples |
| `/voice validate --name [name] --content [file]` | Validate content against voice profile |
| `/voice compare --name [name] [topic]` | A/B comparison on topic |
| `/voice compare-voices --voice1 [name] --voice2 [name]` | Compare two voice profiles |
| `/voice show --name [name]` | Display voice profile.json |
| `/voice list` | List all available voices |
| `/voice check --name [name] --content [file]` | Quick banned pattern check |

---

## API Usage (Web App Integration)

The scripts can be imported as modules:

```python
# Import analyzers
from voice_analyzer import analyze_samples, compare_profiles
from voice_validator import validate_content, check_banned_patterns

# Analyze samples -> profile
profile = analyze_samples(["sample1.md", "sample2.md", "sample3.md"])
print(profile.to_dict())

# Compare two profiles
comparison = compare_profiles(profile1, profile2)
print(comparison)

# Validate content against profile
result = validate_content(
    content=content_text,
    profile=profile_dict,
    voice="your-voice"
)
print(f"Pass: {result.passed}, Score: {result.score}")
for v in result.violations:
    print(f"  [{v.severity}] {v.message}")

# Quick banned check only
from voice_validator import load_banned_patterns, check_banned_patterns
banned = load_banned_patterns()
violations = check_banned_patterns(content_text, banned, voice="your-voice")
```

Future: `scripts/voice_generator.py` will generate CLAUDE.md files for external users who want voice profiles without Claude Code access.

---

## Integration with Content Creation

After calibration, use the voice profile when:

1. **Creating new posts**: Load SKILL.md before writing
2. **Editing drafts**: Validate against profile.json
3. **Review mode**: Compare draft patterns to profile metrics

Validation command for drafts:

```bash
python3 ~/.claude/scripts/voice-validator.py validate \
  --content draft.md \
  --profile skills/voice-{name}/profile.json \
  --voice {name} \
  --format text \
  --verbose
```

The profile is NOT automatically applied. Invoke explicitly:
- "Write [topic] using my voice profile"
- "Review this draft against my voice profile"
- "Validate this content against the voice"
