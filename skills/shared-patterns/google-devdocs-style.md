# Google Developer Documentation Style standard

Construction rules for clear, active, reader-first prose — adapted from the Google Developer Documentation Style Guide. Governs *how* a sentence is built; the Dense-Complete standard still governs *how long* it is.

## Scope

Governs **every generation**, no exception: replies to the user, plain-text output and reports, the model's own thinking, skill/instruction/reference files, and code comments. On any construction conflict, **Google wins**. On length, Dense-Complete wins (see Conflict Rule).

## Voice & tone

| Rule | ✓ | ✗ |
|---|---|---|
| Conversational, not slang or frivolous — a knowledgeable friend, not pedantic | "This API lets you collect data about what your users like." | "Dude! This API is totally awesome!" |
| Not stiff or bureaucratic either | (as above) | "The API may enable the acquisition of information pertaining to user preferences." |
| No placeholder phrases ("please note", "at this time"), no "let's", no internet slang | "This release adds two endpoints." | "Please note that at this time this release adds two endpoints." |
| No exclamation marks | "The build succeeded." | "The build succeeded!" |
| No buzzwords, jargon, cuteness, figurative language, or pop-culture references | "Delete the file." | "Nuke it from orbit." |
| Drop "please" from instructions | "To view the document, click View." | "To view the document, please click View." |

## Active voice

| Rule | ✓ | ✗ |
|---|---|---|
| Use active voice; name who performs the action | "Send a query to the service. The server sends an acknowledgment." | "The service is queried, and an acknowledgment is sent." |
| Recast "by" constructions with the actor as subject | "The client retries the request." | "The request is retried by the client." |

Passive is fine when it earns it: emphasize the object ("The file is saved."), de-emphasize an obvious subject ("Over 50 conflicts were found."), or the actor is irrelevant ("The database was purged in January.").

## Person

| Rule | ✓ | ✗ |
|---|---|---|
| Second person "you", not "we" | "This guide shows how you can create a website." | "This guide shows how we can create a website." |
| Imperative mood for reader actions ("you" implied) | "Click Submit." | "You should click Submit." |
| First-person plural only for the org as author | "Example Org provides A and B, but we don't provide C." | (avoid "we" for the reader) |

## Procedures & instructions

| Rule | ✓ | ✗ |
|---|---|---|
| Put location/context before the action | "In Google Docs, click File > New > Document." | "Click File > New > Document in Google Docs." |
| State the goal before the action | "To start a new document, click File > New > Document." | "Click File > New > Document to start a new document." |
| Conditional: prerequisite before the directive | "If the build fails, check the logs." | "Check the logs if the build fails." |
| Numbered steps for sequences, imperative verb first; single step → bullet | "1. Open the file. 2. Edit the value." | "First you open the file, then the value gets edited." |
| Mark optional steps; combine click sequences with ">" | "Optional: Rename the file." | "You can rename the file (this step is not required)." |
| One reader decision per step; no keyboard shortcuts; no directional language (above/below) | "In the sidebar, click Settings." | "Click the Settings option shown above (or press Ctrl+,)." |

## Formatting

| Rule | ✓ | ✗ |
|---|---|---|
| Sentence case for titles and headings | "Set up the client" | "Set Up The Client" |
| Numbered lists for sequences, bulleted for unordered sets | (sequence → 1., 2., 3.) | (sequence → bullets) |
| Serial (Oxford) comma | "agents, skills, and hooks" | "agents, skills and hooks" |
| Code font for code, commands, filenames, and literal values | Run `ruff check .`. | Run ruff check . |
| Bold for UI element names | Click **Save**. | Click Save. |
| Descriptive link text, never "click here" | See the [style guide](https://example.com). | See the guide [here](https://example.com). |
| Unambiguous dates; alt text for images | "2026-08-17" | "08/17/26" |

## Global audience

| Rule | ✓ | ✗ |
|---|---|---|
| Avoid culturally specific references; write for varied English reading levels | "This happens twice a year." | "This happens around tax season." |
| Simple, consistent wording aids translation; vary sentence openings; read aloud to catch clunk | "Open the file. Then edit the value." | "Open the file. Subsequently, modification of the value should be undertaken." |

## Conflict Rule with Dense-Complete

Google says "be conversational and friendly"; Dense-Complete says "cut every word that carries no instruction." Reconcile by precedence, highest first:

1. **COMPLETENESS FLOOR (highest, beats both below)**: neither warmth nor compression may drop a required instruction, rule, condition, or decision. If shortening would remove a required point, keep the point. This is Dense-Complete's own rule 6 (Completeness), surfaced here as the tiebreaker: content is fixed, wording is negotiable.
   - ✓ "Delete the file only after the user confirms." — keeps the condition.
   - ✗ "Delete the file." — compresses away the required "only after the user confirms" condition.
2. **Google wins on CONSTRUCTION**: active voice, second person ("you"), present tense, conditions/context/goal BEFORE the instruction, imperative steps, sentence-case headings, numbered-vs-bulleted lists, serial commas, descriptive link text, code font, no "please", no exclamation marks, write for a global audience.
3. **Dense-Complete governs LENGTH**, but only after the floor is satisfied: cut words that carry no instruction, rule, or decision. Warmth never adds a sentence that carries none of those. Friendly ≠ filler.

Construction (rule 2) and length (rule 3) are mostly orthogonal; their only overlap is "friendly filler," which rule 3 caps. The floor (rule 1) sits above both: shorten and restyle freely until a required point would drop, then stop.

## Attribution

Adapted from the Google Developer Documentation Style Guide (developers.google.com/style), licensed CC BY 4.0. Rules drawn from its tone, voice, person, procedures, and highlights pages.

## Propagation

**Wired in.** This standard now applies alongside Dense-Complete, reproduced in the same three high-traffic surfaces that carry Dense-Complete: `CLAUDE.md`, `agents/base-instructions.md`, and the `/do` router injection (`skills/meta/do/SKILL.md`). The blind A/B eval was a wash (each arm placed first once); the user judged the combined config (Google construction + Dense-Complete length) cleanest on all three prompts and made this call, with the completeness floor added to fix the one defect the eval exposed (the combined arm dropped a required point twice). Precedence in every surface: completeness floor first (never drop a required point), then Google construction, then Dense-Complete length.

This file holds the canonical wording. Edit it first, then sync the three surfaces to match.
