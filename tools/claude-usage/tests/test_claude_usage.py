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


def test_next_fetch_time():
    assert claude_usage.next_fetch_time(120.0, 60) == 180
    assert claude_usage.next_fetch_time(165.0, 60) == 180
    # Too close to the boundary, so the one after
    assert claude_usage.next_fetch_time(175.0, 60) == 240
    assert claude_usage.next_fetch_time(100.0, 180) == 180
