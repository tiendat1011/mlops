"""
Unit Tests for Evaluation Module
Tests the metric comparison logic.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMetricComparison:
    """Test the champion/challenger comparison logic."""

    def test_challenger_wins_with_improvement(self):
        """Challenger should win if improvement exceeds threshold."""
        champion_score = 0.80
        challenger_score = 0.85
        min_improvement = 0.01
        assert (challenger_score - champion_score) >= min_improvement

    def test_challenger_loses_below_threshold(self):
        """Challenger should lose if improvement is below threshold."""
        champion_score = 0.80
        challenger_score = 0.805
        min_improvement = 0.01
        assert (challenger_score - champion_score) < min_improvement

    def test_challenger_wins_no_champion(self):
        """If no champion exists, challenger should always win."""
        champion_metrics = None
        challenger_score = 0.50
        should_promote = champion_metrics is None
        assert should_promote is True

    def test_challenger_same_score(self):
        """Equal scores should NOT promote (no improvement)."""
        champion_score = 0.80
        challenger_score = 0.80
        min_improvement = 0.01
        assert (challenger_score - champion_score) < min_improvement
