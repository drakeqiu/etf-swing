from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_data() -> pd.DataFrame:
    close = np.array(
        [100.0] * 75
        + list(np.linspace(101, 180, 45))
        + [180.0] * 20
        + list(np.linspace(179, 70, 65))
    )
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=pd.date_range("2025-01-01", periods=len(close), freq="B"),
    )
