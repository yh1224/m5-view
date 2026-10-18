import claude_usage


def test_next_backoff():
    values = []
    current = 0
    for _ in range(7):
        current = claude_usage.next_backoff(current)
        values.append(current)
    assert values == [30, 60, 120, 240, 480, 600, 600]


def test_next_minute():
    assert claude_usage.next_minute(120.0) == 180
    assert claude_usage.next_minute(179.9) == 180
