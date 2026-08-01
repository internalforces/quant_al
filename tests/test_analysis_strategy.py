import pandas as pd
import pytest

from backend.services.strategy import apply_strategy_returns


def test_signal_is_applied_from_the_next_open_to_open_interval():
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.01, 103.0301],
            "signal": [1, 0, 0, 0],
        }
    )

    result = apply_strategy_returns(frame)

    assert result["strategy_return"].tolist() == pytest.approx([0.0, 0.01, 0.01, 0.0])


def test_short_position_inverts_the_underlying_return_and_applies_loss_limit():
    frame = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 102.0],
            "signal": [-1, 0, 0],
        }
    )

    result = apply_strategy_returns(frame)

    assert result["strategy_return"].tolist() == pytest.approx([0.0, -0.015, 0.0])
