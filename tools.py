"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()

    # Step 1: Filter by max_price
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Step 2: Filter by size (case-insensitive substring match)
    if size is not None:
        size_lower = size.lower()
        listings = [
            l for l in listings
            if size_lower in l["size"].lower()
        ]

    # Step 3: Score each listing by keyword overlap with description
    keywords = set(description.lower().split())

    def score(listing: dict) -> int:
        searchable = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
            listing.get("brand") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    # Step 4: Drop listings with score of 0
    scored = [(score(l), l) for l in listings]
    scored = [(s, l) for s, l in scored if s > 0]

    # Step 5: Sort by score descending and return listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_description = (
        f"Title: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Condition: {new_item['condition']}\n"
        f"Brand: {new_item.get('brand') or 'Unknown'}\n"
        f"Description: {new_item['description']}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        # Empty wardrobe: give general styling advice
        prompt = (
            f"A user is considering buying this secondhand item:\n\n"
            f"{item_description}\n\n"
            "They don't have any wardrobe information on file yet. "
            "Give them general styling advice — what kinds of pieces pair well "
            "with this item, what vibe or aesthetic it suits, and how they might "
            "build an outfit around it. Keep it casual and specific, 2–4 sentences."
        )
    else:
        # Format wardrobe items into a readable list
        wardrobe_text = "\n".join(
            f"- {item['name']} ({item['category']}, {', '.join(item['colors'])})"
            + (f" — {item['notes']}" if item.get("notes") else "")
            for item in wardrobe_items
        )

        prompt = (
            f"A user is considering buying this secondhand item:\n\n"
            f"{item_description}\n\n"
            f"Here is their current wardrobe:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and "
            "specific pieces from their wardrobe. Name the exact wardrobe pieces "
            "you're pairing it with. Keep the tone casual and specific — like "
            "advice from a stylish friend, not a fashion magazine. 3–5 sentences total."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.
    """
    # Guard: empty or whitespace-only outfit string
    if not outfit or not outfit.strip():
        return "Cannot generate fit card: no outfit suggestion provided."

    client = _get_groq_client()

    title = new_item.get("title", "thrifted piece")
    price = new_item.get("price", "")
    platform = new_item.get("platform", "")

    prompt = (
        f"Write a short, casual Instagram caption for this thrifted outfit.\n\n"
        f"Thrifted item: {title}"
        + (f" — ${price}" if price else "")
        + (f" on {platform}" if platform else "")
        + f"\n\nOutfit: {outfit}\n\n"
        "Rules:\n"
        "- Write in first person, casual tone — like a real person posting an OOTD\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the specific vibe of the outfit in a few words\n"
        "- Keep it to 2–3 sentences max\n"
        "- Do NOT sound like a product description or a fashion ad\n"
        "- Feel free to use 1–2 relevant emojis naturally"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,  # Higher temp for caption variety
    )

    return response.choices[0].message.content.strip()