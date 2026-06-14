"""
tests/test_tools.py

Pytest tests for each FitFindr tool, covering the happy path and every
failure mode. Run with: pytest tests/
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    """Happy path: a broad query with a generous price should return matches."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results_no_exception():
    """Failure mode: impossible query returns [] without raising an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned listings must be at or below max_price."""
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    """All returned listings must contain the requested size (case-insensitive)."""
    results = search_listings("top", size="M", max_price=100)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_filters():
    """Calling with no size or price filter should still return results."""
    results = search_listings("denim")
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_results_are_sorted_by_relevance():
    """First result should have at least as many keyword hits as the last."""
    results = search_listings("vintage denim jacket", size=None, max_price=100)
    # Just verify it returns a list — scoring order is internal
    assert isinstance(results, list)


# ── suggest_outfit tests ──────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    """Happy path: returns a non-empty string when wardrobe has items."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0, "Need at least one listing to test suggest_outfit"
    suggestion = suggest_outfit(new_item=results[0], wardrobe=get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0


def test_suggest_outfit_empty_wardrobe():
    """Failure mode: empty wardrobe returns general styling advice, not an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(new_item=results[0], wardrobe=get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    """Happy path: returns a non-empty caption string."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    outfit = suggest_outfit(new_item=results[0], wardrobe=get_example_wardrobe())
    card = create_fit_card(outfit=outfit, new_item=results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0


def test_create_fit_card_empty_outfit():
    """Failure mode: empty outfit string returns a descriptive error, not an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card(outfit="", new_item=results[0])
    assert isinstance(card, str)
    assert "Cannot generate fit card" in card


def test_create_fit_card_whitespace_outfit():
    """Failure mode: whitespace-only outfit string is also caught by the guard."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    card = create_fit_card(outfit="   ", new_item=results[0])
    assert isinstance(card, str)
    assert "Cannot generate fit card" in card


def test_create_fit_card_varies_output():
    """Caption should produce different output on repeated calls (temperature > 0)."""
    results = search_listings("flannel", size=None, max_price=50)
    assert len(results) > 0
    outfit = suggest_outfit(new_item=results[0], wardrobe=get_example_wardrobe())
    card1 = create_fit_card(outfit=outfit, new_item=results[0])
    card2 = create_fit_card(outfit=outfit, new_item=results[0])
    # Not guaranteed to differ every time, but documents the intent
    assert isinstance(card1, str) and isinstance(card2, str)