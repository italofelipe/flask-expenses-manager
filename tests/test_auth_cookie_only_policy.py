"""SEC-1 — unit tests for the refresh-token cookie-only policy helper.

Isolated tests for `should_omit_refresh_token_in_body` covering both the
per-request header opt-in and the global `AURAXIS_REFRESH_COOKIE_ONLY` flag.
The helper must treat ambiguous header values as opt-out so the body never
silently drops the token.
"""

from __future__ import annotations

import pytest

from app.controllers.auth.cookie_only_policy import (
    COOKIE_ONLY_HEADER,
    should_omit_refresh_token_in_body,
)


def test_header_name_is_x_refresh_cookie_only() -> None:
    assert COOKIE_ONLY_HEADER == "X-Refresh-Cookie-Only"


class TestGlobalFlag:
    def test_global_flag_true_forces_omit_even_without_header(self) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value=None, global_flag=True)
            is True
        )

    def test_global_flag_true_wins_over_header_opt_out(self) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value="0", global_flag=True)
            is True
        )

    def test_global_flag_false_respects_header(self) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value=None, global_flag=False)
            is False
        )
        assert (
            should_omit_refresh_token_in_body(header_value="1", global_flag=False)
            is True
        )


class TestHeaderParsing:
    @pytest.mark.parametrize(
        "value",
        ["1", "true", "TRUE", "True", "yes", "Yes", "on", " 1 ", " true "],
    )
    def test_truthy_values_opt_in(self, value: str) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value=value, global_flag=False)
            is True
        )

    @pytest.mark.parametrize(
        "value",
        ["0", "false", "no", "off", "", "  ", "maybe", "2"],
    )
    def test_non_truthy_values_opt_out(self, value: str) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value=value, global_flag=False)
            is False
        )

    def test_none_header_value_opts_out(self) -> None:
        assert (
            should_omit_refresh_token_in_body(header_value=None, global_flag=False)
            is False
        )
