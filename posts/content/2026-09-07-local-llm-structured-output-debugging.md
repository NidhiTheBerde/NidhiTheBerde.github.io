I was building a two-agent verification pipeline — a Researcher agent that pulls product claims from the web, and a Biologist agent that cross-references each claim against real molecular data from PubChem — using LangChain, LangGraph, and a locally-hosted `llama3.1:8b` via Ollama instead of a hosted frontier model. The orchestration worked perfectly on the first try: the graph executed end to end, tool calls fired correctly, the conditional retry edge routed as designed. The data coming out of it was garbage.

This is a writeup of three specific, reproducible failure modes I hit getting structured output reliable on a small local model, because I couldn't find good documentation on any of them when I went looking.

## Failure 1: enum fields returning full sentences

My schema had fields like this:

```python
overall_verdict: str = Field(
    description="scientifically_supported | partially_supported | unsupported | insufficient_data"
)
```

The model's actual output: `"THE PRODUCT CONTAINS SEVERAL INGREDIENTS THAT CAN PENETRATE THE SKIN, INCLUDING..."` — a full sentence, not one of the four allowed values.

**Root cause:** a `description` is a hint to the model, not a constraint on the generated JSON schema. `str` means "any string." The model was never actually told it could only pick from four values — it just read the description as guidance and free-associated.

**Fix:** use `Literal` instead.

```python
OverallVerdict = Literal[
    "scientifically_supported", "partially_supported", "unsupported", "insufficient_data"
]
overall_verdict: OverallVerdict = "insufficient_data"
```

`Literal` actually changes the generated JSON schema to an `enum`, which is a real constraint under grammar-constrained decoding — the model can no longer emit a token sequence that isn't one of the allowed values. This fixed it immediately.

## Failure 2: a list field that generated 8,000+ repeated fragments

One field, `scientific_references: list[str]`, was supposed to hold a handful of source citations. The actual output had over 8,000 entries — the same three or four short phrases ("PubChem error", "not scientifically plausible", "scientifically plausible") repeating in a loop, alternating, until the response hit its token budget.

**Root cause:** an unbounded list under grammar-constrained JSON generation has no natural stopping signal. Once the model runs out of genuine content to put in the list, there's nothing in the schema telling it "stop now" — it's still grammatically valid to keep emitting array items, so a smaller model will just keep going, degenerating into repetition, until something external (the token limit) cuts it off.

**Fix:** cap every list field explicitly.

```python
scientific_references: list[str] = Field(default_factory=list, max_length=6)
```

`max_length` becomes `maxItems` in the JSON schema, which — under Ollama's grammar-constrained decoding — is enforced at the token-sampling level, not just validated after the fact. The model literally cannot emit a 7th item. This alone should be standard practice for any list field in a structured-output schema targeting a small local model; I'd never needed it with frontier models because they reliably stop on their own.

## Failure 3: a nested list of objects that came back completely empty

This was the hardest one. I had:

```python
active_assessments: list[ActiveAssessment] = Field(default_factory=list, max_length=8)
```

where `ActiveAssessment` was a 12-field object (molecular formula, molecular weight, logP, TPSA, bioavailability assessment, mechanism notes, claim verdict, etc.) — one per ingredient, 7 ingredients expected.

The model's free-text reasoning (from the ReAct tool-calling loop, before structuring) was genuinely good — it had called the PubChem lookup tool for every ingredient and written out real values: *"Ceramide NP: Verified molecular formula: C36H71NO4, Molecular weight: 582.0 Da... XLogP: 12.4..."* etc., for all 7. But when I asked the model to structure that same reasoning into the nested schema, `active_assessments` came back as `[]`. Empty. Every time. I tried:

- Raising the token budget (`num_predict`) from 1500 to 4096 — no change
- Switching LangChain's structured-output strategy from `json_schema` to `function_calling` — this made it *worse*: the model never emitted the "return structured data" tool call at all, and the call returned `None`

**Root cause:** asking a small model to fill a list of several complex nested objects in a single generation is a much harder task than it looks — it has to track object boundaries, remember which ingredient it's on, and correctly route 12 different field types per object, all in one continuous decode. It's not that the model doesn't know the answer (the free text proves it does) — it's that recalling and correctly re-structuring that much information in one shot exceeds what an 8B model does reliably.

**Fix, part one — stop asking the model to recall numbers it already computed.** The molecular formula, weight, logP, and TPSA values were already sitting in the PubChem tool's raw JSON response from earlier in the ReAct transcript. Instead of asking the model to re-transcribe them from its own prose, I parsed them directly out of the tool-call messages:

```python
def _extract_pubchem_results(messages) -> dict[str, dict]:
    call_id_to_name = {}
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") == "pubchem_lookup":
                call_id_to_name[tc["id"]] = tc["args"].get("compound_name", "")
    results = {}
    for m in messages:
        call_id = getattr(m, "tool_call_id", None)
        if call_id in call_id_to_name:
            results[call_id_to_name[call_id]] = json.loads(m.content)
    return results
```

Then I computed the pass/fail penetration rules (`MW < 500`, `1 <= logP <= 4`) in plain Python, not via the LLM. This guarantees the numeric fields are always exactly correct — they're sourced from the actual API response, not from a model's memory of its own paragraph.

**Fix, part two — decompose the list into one structured call per item.** Instead of one call asking for all 7 `ActiveAssessment` objects, I made 7 separate calls, each asking only for the qualitative judgment (bioavailability assessment, mechanism plausibility, notes, claim verdict) for one named ingredient, then assembled the full objects in Python by merging the deterministic PubChem data with each per-ingredient judgment. This is the same "decompose into atomic per-item extraction" pattern that works well for LLM pipelines generally — asking for one thing at a time is dramatically more reliable than asking for N things in a single generation, even when N is small.

## Failure 4 (the subtle one): a schema where every field has a default silently returns all-defaults

After decomposing, I built a small judgment-only schema:

```python
class IngredientJudgment(BaseModel):
    bioavailability_assessment: Literal["high", "medium", "low", "unknown"] = "unknown"
    mechanism_plausible: bool = False
    mechanism_notes: str = ""
    claim_verdict: ClaimVerdict = "insufficient_data"
```

Every single call returned the schema untouched — `"unknown"`, `False`, `""`, `"insufficient_data"` — for every ingredient, even ones where the source text clearly said things like "scientifically plausible" and gave a specific mechanism.

**Root cause:** every field in this schema has a default. That means `{}` is a completely valid response under the schema — the model can technically satisfy the constraint without extracting anything at all. For a small model, that's the path of least resistance, and it took it, every time.

**Fix:** add one required field with no default.

```python
class IngredientJudgment(BaseModel):
    ingredient: str  # required — no default
    bioavailability_assessment: Literal["high", "medium", "low", "unknown"] = "unknown"
    mechanism_plausible: bool = False
    mechanism_notes: str = ""
    claim_verdict: ClaimVerdict = "insufficient_data"
```

I tested this directly, on the same input, with only that one change: the model went from returning all-defaults to correctly extracting real content for every field. My working theory is that a required field with no default forces the model out of "shortcut mode" — it has to actually engage with the source text to produce *something* valid, and that engagement carries over to the neighboring optional fields instead of them getting skipped too.

## The pattern across all four

None of these are bugs in LangChain, LangGraph, or Ollama. They're all instances of the same underlying thing: **a schema that is merely "typeable" by a small model is not the same as a schema that reliably constrains it.** Frontier models are forgiving enough that sloppy schemas mostly work anyway — a plain `str` with a good description, an unbounded list, an all-optional object — because the model has enough capacity to infer intent past the schema's gaps. Small local models don't have that headroom, so every gap in the schema becomes a place where they take the cheapest valid path instead of the correct one.

The practical checklist that came out of this:
- Use `Literal`, not `str` + description, for anything enum-like
- Cap every list field with `max_length` — don't rely on the model to know when to stop
- Don't ask a small model to fill a list of complex nested objects in one shot — decompose into one call per item
- Pull anything deterministic (numbers you already have from a tool call, rule-based computations) out of the LLM's responsibility entirely
- Give every extraction schema at least one required field with no default, so the model can't satisfy it with an empty shortcut

None of this shows up if you only ever test against Claude or GPT-4-class models, because they're good enough to paper over it. It shows up immediately, and confusingly, the moment you swap in a smaller local model — which is exactly the situation a lot of teams are in right now as local/open-weight models get cheap enough to be worth trying for cost or privacy reasons.
