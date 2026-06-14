# FitFindr — planning.md

## What FitFindr Does

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. When a user describes what they're looking for, the agent searches mock thrift listings, suggests a complete outfit using the user's existing wardrobe, and generates a shareable caption for the look. If any tool fails or returns nothing useful, the agent communicates that clearly and stops rather than proceeding with bad input.

---

## Tool Inventory

### Tool 1: `search_listings(description, size, max_price)`

**What it does:** Searches the mock listings dataset and returns items that match the user's description, size, and price ceiling.

**Inputs:**

- `description` (str) — natural language description of the item the user wants (e.g. `"vintage denim jacket"`)
- `size` (str or None) — clothing size filter (e.g. `"M"`, `"S"`); if `None`, no size filtering is applied
- `max_price` (float) — upper price limit in dollars; only listings at or below this price are returned

**Returns:** A list of listing dicts. Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list `[]` if no matches are found — never raises an exception.

**Failure mode:** If result is `[]`, the agent sets `session["error"]` to a specific message telling the user what to try differently (e.g. loosen price, try a different size, broaden description) and returns early without calling any subsequent tools.

---

### Tool 2: `suggest_outfit(new_item, wardrobe)`

**What it does:** Given a specific thrifted item and the user's current wardrobe, calls the LLM to suggest one or more complete outfit combinations.

**Inputs:**

- `new_item` (dict) — the listing dict selected from `search_listings` results (always `results[0]`)
- `wardrobe` (dict) — the user's current wardrobe, sourced from `get_example_wardrobe()` or `get_empty_wardrobe()`

**Returns:** A string describing one or more complete outfit combinations using the new item and existing wardrobe pieces. If `wardrobe["items"]` is empty, returns general styling advice for the item on its own — does not crash or return an empty string.

**Failure mode:** Empty wardrobe is handled gracefully by prompting the LLM to suggest how to style the item independently, without reference to other wardrobe pieces.

---

### Tool 3: `create_fit_card(outfit, new_item)`

**What it does:** Takes the outfit suggestion and the thrifted item and uses the LLM to generate a short, casual, shareable caption — the kind of thing someone would post on Instagram or TikTok.

**Inputs:**

- `outfit` (str) — the outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict) — the same listing dict, used to pull price and platform details for the caption

**Returns:** A short, casual, first-person caption string (1–3 sentences). Must produce different output on repeated calls with the same input (LLM temperature > 0).

**Failure mode:** If `outfit` is an empty string, returns `"Cannot generate fit card: no outfit suggestion provided."` without calling the LLM.

---

## Planning Loop

The agent runs a sequential loop with conditional branching based on what each tool returns. Here is the exact logic:

1. Call `search_listings(description, size, max_price)` with parameters parsed from the user's query.
2. Check if `results` is empty.
   - **If yes:** set `session["error"] = "No listings found for [description] in size [size] under $[max_price]. Try a higher price or a different size."` and return session immediately. Do not call `suggest_outfit`.
   - **If no:** set `session["selected_item"] = results[0]` and continue.
3. Call `suggest_outfit(new_item=session["selected_item"], wardrobe=wardrobe)`.
4. Set `session["outfit_suggestion"]` to the returned string.
5. Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.
6. Set `session["fit_card"]` to the returned string.
7. Return session.

The agent never calls all three tools unconditionally. Step 2 is the only branch point — if `search_listings` returns nothing, the loop exits immediately.

---

## Architecture

```
User query
    |
    ▼
Planning Loop ──────────────────────────────────────┐
    |                                                |
    ├─► search_listings(description, size,           |
    |        max_price)                              |
    |        | results=[]                            |
    |        └──► session["error"] = "..."  ──► return
    |        | results=[item, ...]                   |
    |        ▼                                       |
    |   session["selected_item"] = results[0]        |
    |        |                                       |
    ├─► suggest_outfit(selected_item, wardrobe)      |
    |        |                                       |
    |   session["outfit_suggestion"] = "..."         |
    |        |                                       |
    └─► create_fit_card(outfit_suggestion,           |
             selected_item)                          |
             |                                       |
        session["fit_card"] = "..."                  |
             |                                       |
             ▼                                       |
        Return session  ◄───────────────────────────┘
```

---

## State Management

The session dict is the single source of truth across all tool calls. It is initialized before the loop and mutated at each step:

```python
session = {
    "query": <original user input>,
    "selected_item": None,
    "outfit_suggestion": None,
    "fit_card": None,
    "error": None
}
```

- `selected_item` is set after `search_listings` and read directly by both `suggest_outfit` and `create_fit_card` — the user never re-enters it.
- `outfit_suggestion` is set after `suggest_outfit` and read by `create_fit_card`.
- `error` is set only when `search_listings` returns empty; all other fields remain `None` in that case.
- No value is hardcoded between steps. Every tool receives its inputs from the session dict.

---

## Error Handling

| Tool              | Failure condition            | Agent response                                                                                                                                                             |
| ----------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `search_listings` | Returns `[]`                 | Sets `session["error"]` with specific retry advice (loosen price, try different size, broaden description). Returns session immediately. `suggest_outfit` is never called. |
| `suggest_outfit`  | `wardrobe["items"]` is empty | Returns a general styling advice string for the item alone. Does not crash or return empty string.                                                                         |
| `create_fit_card` | `outfit` is an empty string  | Returns `"Cannot generate fit card: no outfit suggestion provided."` without calling the LLM.                                                                              |

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**

<!-- What does the agent do first? Which tool is called? With what input? -->

**Step 2:**

<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:**

<!-- Continue until the full interaction is complete -->

**Final output to user:**

<!-- What does the user actually see at the end? -->
