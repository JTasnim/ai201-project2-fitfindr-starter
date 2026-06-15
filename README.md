# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, FitFindr searches mock thrift listings, suggests a complete outfit using the user's existing wardrobe, and generates a shareable caption for the look.

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Add your Groq API key to a .env file
echo "GROQ_API_KEY=your_key_here" > .env

# Launch the Gradio UI
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

Searches the mock listings dataset and returns matching items sorted by relevance.

| Parameter     | Type          | Meaning                                                                                        |
| ------------- | ------------- | ---------------------------------------------------------------------------------------------- |
| `description` | str           | Natural language keywords (e.g. `"vintage graphic tee"`)                                       |
| `size`        | str or None   | Size filter; case-insensitive substring match so `"M"` catches `"S/M"`; `None` skips filtering |
| `max_price`   | float or None | Upper price ceiling inclusive; `None` skips filtering                                          |

**Returns:** `list[dict]` — matching listing dicts sorted by keyword overlap score, highest first. Returns `[]` on no matches — never raises an exception.

**Each listing dict contains:** `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`

---

### `suggest_outfit(new_item, wardrobe)`

Calls the LLM to suggest 1–2 complete outfit combinations using the thrifted item and the user's wardrobe.

| Parameter  | Type | Meaning                                                                    |
| ---------- | ---- | -------------------------------------------------------------------------- |
| `new_item` | dict | A listing dict — the item the user is considering buying                   |
| `wardrobe` | dict | Wardrobe dict with an `items` key containing a list of wardrobe item dicts |

**Returns:** `str` — outfit suggestion. If `wardrobe["items"]` is empty, returns general styling advice for the item on its own rather than raising an exception or returning an empty string.

---

### `create_fit_card(outfit, new_item)`

Calls the LLM to generate a short, casual, shareable caption — the kind of thing someone would post on Instagram or TikTok.

| Parameter  | Type | Meaning                                                           |
| ---------- | ---- | ----------------------------------------------------------------- |
| `outfit`   | str  | The outfit suggestion string from `suggest_outfit`                |
| `new_item` | dict | The listing dict, used to pull price and platform for the caption |

**Returns:** `str` — a 2–3 sentence first-person caption. If `outfit` is empty or whitespace-only, returns `"Cannot generate fit card: no outfit suggestion provided."` without calling the LLM. Uses temperature 0.9 so captions vary on repeated calls.

---

## How the Planning Loop Works

The agent runs a sequential loop with one branch point — the result of `search_listings`:

```
User query
    │
    ▼
_parse_query() → extracts description, size, max_price via regex
    │
    ▼
search_listings(description, size, max_price)
    │
    ├── results == [] ──► session["error"] = specific retry message
    │                     return session immediately
    │                     (suggest_outfit is never called with empty input)
    │
    └── results != [] ──► session["selected_item"] = results[0]
                              │
                              ▼
                          suggest_outfit(selected_item, wardrobe)
                              │
                          session["outfit_suggestion"] = "..."
                              │
                              ▼
                          create_fit_card(outfit_suggestion, selected_item)
                              │
                          session["fit_card"] = "..."
                              │
                              ▼
                          return session
```

The agent never calls all three tools unconditionally. If `search_listings` returns nothing, the loop exits immediately with a helpful error message and never passes empty input to the LLM tools.

---

## State Management

A session dict is initialized at the start of each interaction and mutated at each step. It is the single source of truth — no values are hardcoded between steps.

```python
session = {
    "query": <original user input>,
    "parsed": {"description": ..., "size": ..., "max_price": ...},
    "search_results": [...],       # full list from search_listings
    "selected_item": None,         # set to results[0] after successful search
    "wardrobe": <wardrobe dict>,
    "outfit_suggestion": None,     # set after suggest_outfit
    "fit_card": None,              # set after create_fit_card
    "error": None,                 # set only on early termination
}
```

`selected_item` flows directly from `search_listings` into both `suggest_outfit` and `create_fit_card` — the user never re-enters it. `outfit_suggestion` flows directly from `suggest_outfit` into `create_fit_card`.

---

## Error Handling

| Tool              | Failure condition               | What the agent does                                                                                                                                                   |
| ----------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `search_listings` | Returns `[]`                    | Sets `session["error"]` with specific retry advice (try higher price, different size, broader terms). Returns session immediately — `suggest_outfit` is never called. |
| `suggest_outfit`  | `wardrobe["items"]` is empty    | Prompts the LLM for general styling advice instead of outfit combinations. Returns a non-empty string — does not crash.                                               |
| `create_fit_card` | `outfit` is empty or whitespace | Returns `"Cannot generate fit card: no outfit suggestion provided."` without calling the LLM.                                                                         |

**Concrete example from testing:**

Query: `"designer ballgown size XXS under $5"`

```
search_listings("designer ballgown", size="XXS", max_price=5.0) → []
session["error"] = "No listings found for 'designer ballgown' in size XXS under $5.
                    Try a higher price, a different size, or broader search terms."
session["outfit_suggestion"] = None
session["fit_card"] = None
→ returned immediately, suggest_outfit never called
```

---

## Spec Reflection

**One way the spec helped:** Writing the planning loop logic in `planning.md` before any code made the branch condition explicit — "if results is empty, return early" — which meant the implementation was a direct translation rather than a design decision made under pressure.

**One way implementation diverged:** The spec described parsing size with patterns like "in M" or "size M", but in practice bare "in M" without the word "size" matched too aggressively — words ending in those letters were being stripped from the description. The final implementation requires the word "size" to be present, which is more conservative but more accurate.

---

## AI Usage

**Instance 1 — implementing `search_listings`:**
I gave Claude the Tool 1 spec block from `planning.md` (inputs, return value, failure mode) and asked it to implement the function using `load_listings()`. The generated code used exact string matching for size, so "M" would not match "S/M". I caught this during review before running it and asked Claude to fix the size filter to use case-insensitive substring matching. I then verified with three test queries: one returning results, one returning `[]`, and one checking the price ceiling.

**Instance 2 — implementing `_parse_query`:**
I gave Claude the Planning Loop section of `planning.md` and asked it to implement a regex-based query parser. The first version matched bare numbers for price, which caused "90s track jacket" to parse as `max_price=90.0`. I caught this by running the parser against all five example queries before wiring it into `run_agent`. I asked Claude to fix the price regex to require an explicit `$` sign or a keyword like "under/below", then re-verified all five queries parsed correctly.
