"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.
    """
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns.

    Examples:
        "vintage graphic tee under $30, size M"
        → {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}

        "flannel shirt"
        → {"description": "flannel shirt", "size": None, "max_price": None}

    Strategy:
        1. Extract max_price from patterns like "under $30", "$30", "under 30"
        2. Extract size from patterns like "size M", "size S/M", "in M"
        3. Remove price/size fragments from the query to get a clean description
    """
    # Extract max_price — requires explicit $ sign OR "under/below" keyword
    # This avoids treating "90s" or "70s" as prices
    price_match = re.search(
        r'(?:under|below|max|up\s+to)\s+\$?(\d+(?:\.\d+)?)'
        r'|\$(\d+(?:\.\d+)?)',
        query, re.IGNORECASE
    )
    if price_match:
        max_price = float(price_match.group(1) or price_match.group(2))
    else:
        max_price = None

    # Extract size — requires "size" or "in size" prefix to avoid false matches
    # Matches: "size M", "size S/M", "in size XL", "size 8"
    size_match = re.search(
        r'(?:in\s+)?size\s+([XxSsMmLl]{1,3}(?:/[XxSsMmLl]{1,3})?|\d+)',
        query,
        re.IGNORECASE
    )
    size = size_match.group(1).upper() if size_match else None

    # Clean description: remove price and size fragments
    description = query
    description = re.sub(
        r'(?:under|below|max|up\s+to)\s+\$?\d+(?:\.\d+)?',
        '', description, flags=re.IGNORECASE
    )
    description = re.sub(r'\$\d+(?:\.\d+)?', '', description, flags=re.IGNORECASE)
    description = re.sub(r'\d+(?:\.\d+)?\s*dollars?', '', description, flags=re.IGNORECASE)
    description = re.sub(
        r'(?:in\s+)?size\s+[XxSsMmLl]{1,3}(?:/[XxSsMmLl]{1,3})?',
        '', description, flags=re.IGNORECASE
    )
    description = re.sub(r'(?:in\s+)?size\s+\d+', '', description, flags=re.IGNORECASE)
    description = re.sub(r'\s+', ' ', description).strip(' ,')

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
        wardrobe: User's wardrobe dict

    Returns:
        The session dict. Check session["error"] first — if not None,
        the interaction ended early and outfit_suggestion/fit_card will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into description, size, max_price
    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 3: Search listings
    results = search_listings(description=description, size=size, max_price=max_price)
    session["search_results"] = results

    # Branch: no results → set error and return early
    if not results:
        size_note = f" in size {size}" if size else ""
        price_note = f" under ${max_price:.0f}" if max_price else ""
        session["error"] = (
            f"No listings found for '{description}'{size_note}{price_note}. "
            "Try a higher price, a different size, or broader search terms."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    outfit_suggestion = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=wardrobe,
    )
    session["outfit_suggestion"] = outfit_suggestion

    # Step 6: Create fit card
    fit_card = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")