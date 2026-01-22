#!/usr/bin/env python3
"""
rasp-shutter アプリケーション用のユーティリティ関数
"""

import functools
import os
from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable)


def is_dummy_mode() -> bool:
    """DUMMY_MODEが有効かどうかを返す

    テストやハードウェアなしでの動作確認時に使用される
    環境変数 DUMMY_MODE が "true" の場合に True を返す

    Returns
    -------
        bool: DUMMY_MODEが有効な場合 True

    """
    return os.environ.get("DUMMY_MODE", "false") == "true"


def check_dummy_mode_for_api() -> tuple[dict[str, str], int] | None:
    """テストAPIのDUMMY_MODEチェック

    DUMMY_MODEが有効でない場合にエラーレスポンスを返す
    テスト用APIで共通して使用するガード関数

    Returns
    -------
        tuple[dict[str, str], int] | None:
            DUMMY_MODEが無効の場合はエラーレスポンス (dict, 403)
            DUMMY_MODEが有効の場合は None

    Examples
    --------
        >>> error = check_dummy_mode_for_api()
        >>> if error:
        >>>     return error

    """
    if not is_dummy_mode():
        return {"error": "Test API is only available in DUMMY_MODE"}, 403
    return None


def is_pytest_running() -> bool:
    """pytest実行中かどうかを返す

    テスト環境でのみ特定の処理を行う場合に使用する。
    環境変数 PYTEST_CURRENT_TEST が設定されている場合に True を返す。

    Returns
    -------
        bool: pytest実行中の場合 True

    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def require_dummy_mode(f: F) -> F:
    """DUMMY_MODE必須デコレータ

    テスト用APIでDUMMY_MODEが有効でない場合に403エラーを返す。
    各関数でのインラインチェックを不要にする。

    Examples
    --------
        >>> @blueprint.route("/api/test/example", methods=["POST"])
        >>> @require_dummy_mode
        >>> def test_example():
        >>>     return {"success": True}

    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        error = check_dummy_mode_for_api()
        if error:
            return error
        return f(*args, **kwargs)

    # functools.wraps で型情報が保持されないため
    return decorated_function  # type: ignore[return-value]
