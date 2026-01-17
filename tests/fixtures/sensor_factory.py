#!/usr/bin/env python3
"""センサーデータファクトリー

テスト用のセンサーデータを生成するファクトリークラスを提供します。
"""

from typing import Any, ClassVar


class SensorDataFactory:
    """センサーデータ生成ファクトリー"""

    # 明るい状態のデフォルト値
    BRIGHT_DEFAULTS: ClassVar[dict[str, int]] = {
        "solar_rad": 200,
        "lux": 2000,
        "altitude": 50,
    }

    # 暗い状態のデフォルト値
    DARK_DEFAULTS: ClassVar[dict[str, int]] = {
        "solar_rad": 10,
        "lux": 10,
        "altitude": 0,
    }

    @classmethod
    def bright(cls) -> dict[str, Any]:
        """明るい状態のセンサーデータを生成

        Returns:
            明るい状態のセンサーデータ
        """
        return cls.custom(
            solar_rad=cls.BRIGHT_DEFAULTS["solar_rad"],
            lux=cls.BRIGHT_DEFAULTS["lux"],
            altitude=cls.BRIGHT_DEFAULTS["altitude"],
        )

    @classmethod
    def dark(cls) -> dict[str, Any]:
        """暗い状態のセンサーデータを生成

        Returns:
            暗い状態のセンサーデータ
        """
        return cls.custom(
            solar_rad=cls.DARK_DEFAULTS["solar_rad"],
            lux=cls.DARK_DEFAULTS["lux"],
            altitude=cls.DARK_DEFAULTS["altitude"],
        )

    @classmethod
    def custom(
        cls,
        solar_rad: float = 100,
        lux: float = 1000,
        altitude: float = 30,
        solar_rad_valid: bool = True,
        lux_valid: bool = True,
        altitude_valid: bool = True,
    ) -> dict[str, Any]:
        """カスタムセンサーデータを生成

        Args:
            solar_rad: 日射量 (W/m^2)
            lux: 照度 (lux)
            altitude: 太陽高度 (度)
            solar_rad_valid: 日射量が有効かどうか
            lux_valid: 照度が有効かどうか
            altitude_valid: 太陽高度が有効かどうか

        Returns:
            センサーデータ
        """
        return {
            "solar_rad": {"valid": solar_rad_valid, "value": solar_rad},
            "lux": {"valid": lux_valid, "value": lux},
            "altitude": {"valid": altitude_valid, "value": altitude},
        }

    @classmethod
    def invalid_lux(cls) -> dict[str, Any]:
        """照度が無効なセンサーデータを生成

        Returns:
            照度が無効なセンサーデータ
        """
        return cls.custom(
            solar_rad=cls.BRIGHT_DEFAULTS["solar_rad"],
            lux=5000,
            altitude=cls.BRIGHT_DEFAULTS["altitude"],
            lux_valid=False,
        )

    @classmethod
    def invalid_solar_rad(cls) -> dict[str, Any]:
        """日射量が無効なセンサーデータを生成

        Returns:
            日射量が無効なセンサーデータ
        """
        return cls.custom(
            solar_rad=5000,
            lux=cls.BRIGHT_DEFAULTS["lux"],
            altitude=cls.BRIGHT_DEFAULTS["altitude"],
            solar_rad_valid=False,
        )

    @classmethod
    def all_invalid(cls) -> dict[str, Any]:
        """すべてのセンサーが無効なデータを生成

        Returns:
            すべて無効なセンサーデータ
        """
        return cls.custom(
            solar_rad=0,
            lux=0,
            altitude=0,
            solar_rad_valid=False,
            lux_valid=False,
            altitude_valid=False,
        )


# 後方互換性のための定数
SENSOR_DATA_BRIGHT = SensorDataFactory.bright()
SENSOR_DATA_DARK = SensorDataFactory.dark()
