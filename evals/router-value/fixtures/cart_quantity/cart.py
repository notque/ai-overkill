def cart_total(items):
    """Return sum of unit_price times quantity for all line items."""
    return sum(item["unit_price"] for item in items)
