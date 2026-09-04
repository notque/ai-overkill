def sort_prices(records):
    """Return a new stable list in numeric ascending price order."""
    return sorted(records, key=lambda record: record["price"])
