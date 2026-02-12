#!/usr/bin/env python3
# ruff: noqa: S101
"""API スキーマ整合性テスト

フロントエンドが期待する API レスポンス形式とバックエンドの
dataclass 定義が一致していることを確認するテスト。

フロントエンドが TypeScript を使用していないため、
ここでバックエンドの型定義がフロントエンドの期待と一致することを保証します。
"""

import dataclasses
import datetime
import json

import pytest

import rasp_shutter.type_defs


class TestSensorValueSchema:
    """SensorValue API のスキーマ整合性テスト

    フロントエンドコンポーネント: SensorData.vue
    使用箇所: センサー値の表示
    """

    def test_sensor_value_has_valid_field(self) -> None:
        """SensorValue が 'valid' フィールドを持つこと"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        assert "valid" in result, "SensorValue には 'valid' フィールドが必要です"
        assert isinstance(result["valid"], bool)

    def test_sensor_value_has_value_field(self) -> None:
        """SensorValue が 'value' フィールドを持つこと"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        assert "value" in result, "SensorValue には 'value' フィールドが必要です"
        assert isinstance(result["value"], float)

    def test_sensor_value_has_time_field(self) -> None:
        """SensorValue が 'time' フィールドを持つこと"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        assert "time" in result, "SensorValue には 'time' フィールドが必要です"
        assert isinstance(result["time"], datetime.datetime)

    def test_sensor_value_full_structure(self) -> None:
        """SensorValue の完全なフィールド構造を確認"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        expected_fields = {"valid", "value", "time"}
        assert set(result.keys()) == expected_fields, (
            f"SensorValue のフィールドが期待と異なります: {set(result.keys())} != {expected_fields}"
        )

    def test_invalid_sensor_value_structure(self) -> None:
        """無効な SensorValue の構造を確認"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_invalid()
        result = dataclasses.asdict(sensor_value)

        assert result["valid"] is False
        assert result["value"] is None
        assert result["time"] is None


class TestSensorDataSchema:
    """SensorData API のスキーマ整合性テスト

    フロントエンドコンポーネント: SensorData.vue
    エンドポイント: GET /api/sensor
    """

    def test_sensor_data_has_lux_field(self) -> None:
        """SensorData が 'lux' フィールドを持つこと"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_invalid(),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        assert "lux" in result, "SensorData には 'lux' フィールドが必要です"

    def test_sensor_data_has_solar_rad_field(self) -> None:
        """SensorData が 'solar_rad' フィールドを持つこと"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_invalid(),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        assert "solar_rad" in result, "SensorData には 'solar_rad' フィールドが必要です"

    def test_sensor_data_has_altitude_field(self) -> None:
        """SensorData が 'altitude' フィールドを持つこと"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_invalid(),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        assert "altitude" in result, "SensorData には 'altitude' フィールドが必要です"

    def test_sensor_data_full_structure(self) -> None:
        """SensorData の完全なフィールド構造を確認"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_invalid(),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        expected_fields = {"lux", "solar_rad", "altitude"}
        assert set(result.keys()) == expected_fields, (
            f"SensorData のフィールドが期待と異なります: {set(result.keys())} != {expected_fields}"
        )

    def test_sensor_data_nested_structure(self) -> None:
        """SensorData のネストされた SensorValue 構造を確認"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_valid(value=1000.0, time=datetime.datetime.now()),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_valid(
                value=500.0, time=datetime.datetime.now()
            ),
            altitude=rasp_shutter.type_defs.SensorValue.create_valid(
                value=45.0, time=datetime.datetime.now()
            ),
        )
        result = dataclasses.asdict(sensor_data)

        # 各センサー値が SensorValue 構造を持つこと
        for field_name in ["lux", "solar_rad", "altitude"]:
            assert "valid" in result[field_name]
            assert "value" in result[field_name]
            assert "time" in result[field_name]


class TestShutterStateEntrySchema:
    """ShutterStateEntry API のスキーマ整合性テスト

    フロントエンドコンポーネント: ManualEntry.vue
    使用箇所: シャッター状態の表示
    """

    def test_shutter_state_entry_has_name_field(self) -> None:
        """ShutterStateEntry が 'name' フィールドを持つこと"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テストシャッター", state=0)
        result = dataclasses.asdict(entry)

        assert "name" in result, "ShutterStateEntry には 'name' フィールドが必要です"
        assert isinstance(result["name"], str)

    def test_shutter_state_entry_has_state_field(self) -> None:
        """ShutterStateEntry が 'state' フィールドを持つこと"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テストシャッター", state=0)
        result = dataclasses.asdict(entry)

        assert "state" in result, "ShutterStateEntry には 'state' フィールドが必要です"
        assert isinstance(result["state"], int)

    def test_shutter_state_entry_full_structure(self) -> None:
        """ShutterStateEntry の完全なフィールド構造を確認"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テストシャッター", state=1)
        result = dataclasses.asdict(entry)

        expected_fields = {"name", "state"}
        assert set(result.keys()) == expected_fields, (
            f"ShutterStateEntry のフィールドが期待と異なります: {set(result.keys())} != {expected_fields}"
        )

    @pytest.mark.parametrize("state_value", [0, 1, 2])
    def test_shutter_state_valid_values(self, state_value: int) -> None:
        """ShutterStateEntry の state が有効な値 (0, 1, 2) を受け入れること"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テスト", state=state_value)
        result = dataclasses.asdict(entry)

        assert result["state"] == state_value


class TestShutterStateResponseSchema:
    """ShutterStateResponse API のスキーマ整合性テスト

    フロントエンドコンポーネント: ManualControl.vue
    エンドポイント: GET /api/shutter_ctrl/state
    """

    def test_shutter_state_response_has_state_field(self) -> None:
        """ShutterStateResponse が 'state' フィールドを持つこと"""
        response = rasp_shutter.type_defs.ShutterStateResponse()
        result = dataclasses.asdict(response)

        assert "state" in result, "ShutterStateResponse には 'state' フィールドが必要です"
        assert isinstance(result["state"], list)

    def test_shutter_state_response_has_result_field(self) -> None:
        """ShutterStateResponse が 'result' フィールドを持つこと"""
        response = rasp_shutter.type_defs.ShutterStateResponse()
        result = dataclasses.asdict(response)

        assert "result" in result, "ShutterStateResponse には 'result' フィールドが必要です"
        assert isinstance(result["result"], str)

    def test_shutter_state_response_full_structure(self) -> None:
        """ShutterStateResponse の完全なフィールド構造を確認"""
        response = rasp_shutter.type_defs.ShutterStateResponse()
        result = dataclasses.asdict(response)

        expected_fields = {"state", "result"}
        assert set(result.keys()) == expected_fields, (
            f"ShutterStateResponse のフィールドが期待と異なります: {set(result.keys())} != {expected_fields}"
        )

    def test_shutter_state_response_with_entries(self) -> None:
        """ShutterStateResponse に ShutterStateEntry を含む場合の構造を確認"""
        entries = [
            rasp_shutter.type_defs.ShutterStateEntry(name="シャッター1", state=0),
            rasp_shutter.type_defs.ShutterStateEntry(name="シャッター2", state=1),
        ]
        response = rasp_shutter.type_defs.ShutterStateResponse(state=entries, result="success")
        result = dataclasses.asdict(response)

        assert len(result["state"]) == 2
        assert result["state"][0]["name"] == "シャッター1"
        assert result["state"][0]["state"] == 0
        assert result["state"][1]["name"] == "シャッター2"
        assert result["state"][1]["state"] == 1


class TestScheduleEntrySchema:
    """ScheduleEntry (TypedDict) のスキーマ整合性テスト

    フロントエンドコンポーネント: ScheduleSetting.vue
    エンドポイント: GET/POST /api/schedule
    """

    def test_schedule_entry_has_required_fields(self) -> None:
        """ScheduleEntry が必要なすべてのフィールドを持つこと"""
        entry: rasp_shutter.type_defs.ScheduleEntry = {
            "is_active": True,
            "time": "08:00",
            "wday": [False, True, True, True, True, True, False],
            "solar_rad": 100,
            "lux": 1000,
            "altitude": 10,
        }

        expected_fields = {"is_active", "time", "wday", "solar_rad", "lux", "altitude"}
        assert set(entry.keys()) == expected_fields

    def test_schedule_entry_field_types(self) -> None:
        """ScheduleEntry の各フィールドの型を確認"""
        entry: rasp_shutter.type_defs.ScheduleEntry = {
            "is_active": True,
            "time": "08:00",
            "wday": [False, True, True, True, True, True, False],
            "solar_rad": 100,
            "lux": 1000,
            "altitude": 10,
        }

        assert isinstance(entry["is_active"], bool)
        assert isinstance(entry["time"], str)
        assert isinstance(entry["wday"], list)
        assert isinstance(entry["solar_rad"], int)
        assert isinstance(entry["lux"], int)
        assert isinstance(entry["altitude"], int)

    def test_schedule_entry_wday_length(self) -> None:
        """ScheduleEntry の wday が 7 要素であること（日〜土）"""
        entry: rasp_shutter.type_defs.ScheduleEntry = {
            "is_active": True,
            "time": "08:00",
            "wday": [False, True, True, True, True, True, False],
            "solar_rad": 100,
            "lux": 1000,
            "altitude": 10,
        }

        assert len(entry["wday"]) == 7, "wday は 7 要素（日曜〜土曜）である必要があります"
        assert all(isinstance(day, bool) for day in entry["wday"])


class TestScheduleDataSchema:
    """ScheduleData (TypedDict) のスキーマ整合性テスト

    フロントエンドコンポーネント: ScheduleSetting.vue
    エンドポイント: GET/POST /api/schedule
    """

    def test_schedule_data_has_open_field(self) -> None:
        """ScheduleData が 'open' フィールドを持つこと"""
        data: rasp_shutter.type_defs.ScheduleData = {
            "open": {
                "is_active": True,
                "time": "08:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 100,
                "lux": 1000,
                "altitude": 10,
            },
            "close": {
                "is_active": True,
                "time": "18:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 50,
                "lux": 500,
                "altitude": 5,
            },
        }

        assert "open" in data, "ScheduleData には 'open' フィールドが必要です"

    def test_schedule_data_has_close_field(self) -> None:
        """ScheduleData が 'close' フィールドを持つこと"""
        data: rasp_shutter.type_defs.ScheduleData = {
            "open": {
                "is_active": True,
                "time": "08:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 100,
                "lux": 1000,
                "altitude": 10,
            },
            "close": {
                "is_active": True,
                "time": "18:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 50,
                "lux": 500,
                "altitude": 5,
            },
        }

        assert "close" in data, "ScheduleData には 'close' フィールドが必要です"

    def test_schedule_data_full_structure(self) -> None:
        """ScheduleData の完全なフィールド構造を確認"""
        data: rasp_shutter.type_defs.ScheduleData = {
            "open": {
                "is_active": True,
                "time": "08:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 100,
                "lux": 1000,
                "altitude": 10,
            },
            "close": {
                "is_active": True,
                "time": "18:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 50,
                "lux": 500,
                "altitude": 5,
            },
        }

        expected_fields = {"open", "close"}
        assert set(data.keys()) == expected_fields


class TestDataclassSerializability:
    """dataclass の JSON シリアライズ可能性テスト

    Flask の jsonify で正しく変換できることを確認します。
    """

    def test_sensor_value_is_serializable(self) -> None:
        """SensorValue が JSON シリアライズ可能であること"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        # datetime を文字列に変換して JSON シリアライズ
        json_str = json.dumps(result, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert parsed["valid"] is True
        assert parsed["value"] == 100.0

    def test_sensor_data_is_serializable(self) -> None:
        """SensorData が JSON シリアライズ可能であること"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_valid(value=1000.0, time=datetime.datetime.now()),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        json_str = json.dumps(result, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert parsed["lux"]["valid"] is True
        assert parsed["lux"]["value"] == 1000.0

    def test_shutter_state_entry_is_serializable(self) -> None:
        """ShutterStateEntry が JSON シリアライズ可能であること"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テストシャッター", state=1)
        result = dataclasses.asdict(entry)

        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert parsed["name"] == "テストシャッター"
        assert parsed["state"] == 1

    def test_shutter_state_response_is_serializable(self) -> None:
        """ShutterStateResponse が JSON シリアライズ可能であること"""
        entries = [
            rasp_shutter.type_defs.ShutterStateEntry(name="シャッター1", state=0),
            rasp_shutter.type_defs.ShutterStateEntry(name="シャッター2", state=1),
        ]
        response = rasp_shutter.type_defs.ShutterStateResponse(state=entries, result="success")
        result = dataclasses.asdict(response)

        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert len(parsed["state"]) == 2
        assert parsed["result"] == "success"

    def test_schedule_entry_is_serializable(self) -> None:
        """ScheduleEntry (TypedDict) が JSON シリアライズ可能であること"""
        entry: rasp_shutter.type_defs.ScheduleEntry = {
            "is_active": True,
            "time": "08:00",
            "wday": [False, True, True, True, True, True, False],
            "solar_rad": 100,
            "lux": 1000,
            "altitude": 10,
        }

        json_str = json.dumps(entry, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert parsed["is_active"] is True
        assert parsed["time"] == "08:00"

    def test_schedule_data_is_serializable(self) -> None:
        """ScheduleData (TypedDict) が JSON シリアライズ可能であること"""
        data: rasp_shutter.type_defs.ScheduleData = {
            "open": {
                "is_active": True,
                "time": "08:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 100,
                "lux": 1000,
                "altitude": 10,
            },
            "close": {
                "is_active": True,
                "time": "18:00",
                "wday": [False, True, True, True, True, True, False],
                "solar_rad": 50,
                "lux": 500,
                "altitude": 5,
            },
        }

        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert parsed is not None
        assert "open" in parsed
        assert "close" in parsed


class TestNegativeFieldNameChecks:
    """フィールド名の負のテスト（想定外のフィールド名がないこと）

    フロントエンドとの整合性を保つため、予期しないフィールド名が
    追加されていないことを確認します。
    """

    def test_sensor_value_no_unexpected_fields(self) -> None:
        """SensorValue に想定外のフィールドがないこと"""
        sensor_value = rasp_shutter.type_defs.SensorValue.create_valid(
            value=100.0,
            time=datetime.datetime.now(),
        )
        result = dataclasses.asdict(sensor_value)

        allowed_fields = {"valid", "value", "time"}
        unexpected = set(result.keys()) - allowed_fields
        assert not unexpected, f"SensorValue に想定外のフィールドがあります: {unexpected}"

    def test_sensor_data_no_unexpected_fields(self) -> None:
        """SensorData に想定外のフィールドがないこと"""
        sensor_data = rasp_shutter.type_defs.SensorData(
            lux=rasp_shutter.type_defs.SensorValue.create_invalid(),
            solar_rad=rasp_shutter.type_defs.SensorValue.create_invalid(),
            altitude=rasp_shutter.type_defs.SensorValue.create_invalid(),
        )
        result = dataclasses.asdict(sensor_data)

        allowed_fields = {"lux", "solar_rad", "altitude"}
        unexpected = set(result.keys()) - allowed_fields
        assert not unexpected, f"SensorData に想定外のフィールドがあります: {unexpected}"

    def test_shutter_state_entry_no_unexpected_fields(self) -> None:
        """ShutterStateEntry に想定外のフィールドがないこと"""
        entry = rasp_shutter.type_defs.ShutterStateEntry(name="テスト", state=0)
        result = dataclasses.asdict(entry)

        allowed_fields = {"name", "state"}
        unexpected = set(result.keys()) - allowed_fields
        assert not unexpected, f"ShutterStateEntry に想定外のフィールドがあります: {unexpected}"

    def test_shutter_state_response_no_unexpected_fields(self) -> None:
        """ShutterStateResponse に想定外のフィールドがないこと"""
        response = rasp_shutter.type_defs.ShutterStateResponse()
        result = dataclasses.asdict(response)

        allowed_fields = {"state", "result"}
        unexpected = set(result.keys()) - allowed_fields
        assert not unexpected, f"ShutterStateResponse に想定外のフィールドがあります: {unexpected}"


class TestStateToActionText:
    """state_to_action_text 関数のテスト

    フロントエンドのメッセージ表示に使用される変換関数の整合性を確認します。
    """

    def test_open_state_to_action_text(self) -> None:
        """'open' が '開け' に変換されること"""
        result = rasp_shutter.type_defs.state_to_action_text("open")
        assert result == "開け"

    def test_close_state_to_action_text(self) -> None:
        """'close' が '閉め' に変換されること"""
        result = rasp_shutter.type_defs.state_to_action_text("close")
        assert result == "閉め"
