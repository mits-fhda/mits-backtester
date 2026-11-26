"""Smoke tests: the web app runs top to bottom without errors.

They use the offline sample data, so no internet connection is needed.
"""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP_PATH = "../app.py"  # relative to this tests/ folder


def start_app_with_sample_data():
    app = AppTest.from_file(APP_PATH, default_timeout=60)
    app.session_state["source"] = "Sample data"   # pick the data source before the first run
    return app.run()


def test_app_runs_on_sample_data():
    app = start_app_with_sample_data()
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 4   # the four headline numbers


def test_app_shows_error_when_short_window_too_long():
    app = start_app_with_sample_data()
    app.sidebar.slider[0].set_value(150)   # short window
    app.sidebar.slider[1].set_value(100)   # long window, now shorter than the short one
    app.run()
    assert not app.exception
    assert "smaller than the long window" in app.error[0].value
