"""Suíte portátil executada pelos agentes SERMAX em runners Linux."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT))

PATTERNS = (
    "test_sermax_core*.py",
    "test_sermax_dev_*.py",
    "test_sermax_groq_backend.py",
    "test_sermax_workspace.py",
    "test_sermax_executor_tasks.py",
    "test_sermax_jarvis_adapter.py",
    "test_sermax_pestinha_adapter.py",
    "test_sermax_planner_validation.py",
    "test_sermax_safe_calculator.py",
    "test_sermax_widget_neural_integration.py",
    "test_sermax_widget_state.py",
    "test_sermax_historico_seguro.py",
)

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for pattern in PATTERNS:
    suite.addTests(
        loader.discover(
            start_dir=str(TESTS),
            pattern=pattern,
            top_level_dir=str(TESTS),
        )
    )

result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
