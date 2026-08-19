MAX_PAGES = 25
OFFER_LETTER_TARGET_PAGES_1_INDEXED = [1, 6, 7, 8, 11, 12]


def select_target_pages(total_pages: int, doc_type: str) -> list[int]:
    """Return 1-indexed page numbers for extraction."""

    if doc_type == "SIGNED_OFFER_LETTER_JADE":
        return [page for page in OFFER_LETTER_TARGET_PAGES_1_INDEXED if page <= total_pages]
    return list(range(1, min(total_pages, MAX_PAGES) + 1))
