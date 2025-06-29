# Duplicate Code Patterns Analysis for test_basic.py

## 1. Sensor Data Mocking Patterns

### Pattern: Direct sensor_data_mock with scheduler patch

**Count: 9 occurrences**

```python
sensor_data_mock = mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data")
sensor_data_mock.return_value = SENSOR_DATA_[BRIGHT|DARK]
mocker.patch(
    "rasp_shutter.scheduler.rasp_shutter.webapp_sensor.get_sensor_data",
    side_effect=lambda _: sensor_data_mock.return_value,
)
```

**Locations:**

- Line 972-977 (test_schedule_ctrl_auto_close)
- Line 1069-1074 (test_schedule_ctrl_auto_close_dup)
- Line 1184-1189 (test_schedule_ctrl_auto_reopen)
- Line 1394-1399 (test_schedule_ctrl_auto_inactive)
- Line 1432-1437 (test_schedule_ctrl_pending_open)
- Line 1514-1519 (test_schedule_ctrl_pending_open_inactive)
- Line 1616-1621 (test_schedule_ctrl_pending_open_fail)
- Line 1767-1772 (test_schedule_ctrl_pending_open_dup)
- Line 1974-1979, 2036-2043, 2070-2077 (test_schedule_ctrl_control_fail_2, test_schedule_ctrl_invalid_sensor_1/2)

### Pattern: Simple sensor mock without scheduler

**Count: 3 occurrences**

```python
mocker.patch("rasp_shutter.webapp_sensor.get_sensor_data", return_value=SENSOR_DATA_BRIGHT)
```

**Locations:**

- Line 906 (test_schedule_ctrl_execute)
- Line 1693-1694 (test_schedule_ctrl_open_dup)
- Line 1906-1907 (test_schedule_ctrl_control_fail_1)

## 2. HTTP Request Patterns

### Pattern: Schedule control API calls

**Count: 22 occurrences**

```python
response = client.get(
    f"{my_lib.webapp.config.URL_PREFIX}/api/schedule_ctrl",
    query_string={"cmd": "set", "data": json.dumps(schedule_data)},
)
assert response.status_code == 200
```

**Locations:**

- Lines 763-768, 792-797 (test_schedule_ctrl_inactive)
- Lines 824-828, 832-836, 840-844, 848-852, 856-860, 864-868, 872-876, 880-884 (test_schedule_ctrl_invalid)
- Lines 934-938, 997-1001, 1114-1118, 1208-1212, 1408-1411, 1458-1461, 1539-1542, 1574-1577, 1648-1652, 1726-1730, 1813-1817, 1938-1941, 2010-2014, 2050-2054, 2084-2088, 2131-2135, 2140-2143 (various test functions)

### Pattern: Shutter control API calls for manual control

**Count: 30 occurrences**

```python
response = client.get(
    f"{my_lib.webapp.config.URL_PREFIX}/api/shutter_ctrl",
    query_string={
        "cmd": 1,
        ["index": N,]  # optional
        "state": "[open|close]",
    },
)
assert response.status_code == 200
assert response.json["result"] == "success"
```

**Locations:**

- Lines 472-483, 486-495 (test_valve_ctrl_manual_single_1)
- Lines 502-513, 516-525 (test_valve_ctrl_manual_single_2)
- Lines 533-543, 546-556, 559-569, 579-589, 602-611, 620-629 (test_valve_ctrl_manual_all)
- Lines 696-706, 716-725 (test_valve_ctrl_manual_single_fail)
- Lines 908-917, 921-931 (test_schedule_ctrl_execute)
- Lines 982-991, 1089-1099 (test_schedule_ctrl_auto_close, test_schedule_ctrl_auto_close_dup)
- Lines 1191-1200, 1442-1451, 1521-1530, 1626-1635, 1704-1713, 1777-1787, 1788-1798, 1917-1926, 1982-1991 (various test functions)

### Pattern: Reading shutter control state

**Count: 3 occurrences**

```python
response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/api/shutter_ctrl")
assert response.status_code == 200
assert response.json["result"] == "success"
```

**Locations:**

- Lines 424-429 (test_shutter_ctrl_read)
- Lines 445-452, 459-466 (test_shutter_ctrl_inconsistent_read)

## 3. Common Test Setup Patterns

### Pattern: Time machine movement with sleep

**Count: 40+ occurrences**

```python
move_to(time_machine, time_[morning|evening](N))
time.sleep(1)  # Restored to 1s for scheduler [job]
```

**Locations:**

- Throughout scheduler-based tests (lines 770-815, 942-945, 1005-1008, 1121-1124, 1222-1227, etc.)

### Pattern: Test data generation

**Count: 22 occurrences**

```python
schedule_data = gen_schedule_data()
```

**Locations:**

- Lines 760, 822, 830, 838, 846, 854, 862, 870, 878, 932, 994, 1111, 1206, 1404, 1454, 1536, 1646, 1722, 1810, 1936, 2008, 2048, 2082, 2130, 2138

## 4. Log Checking Patterns

### Pattern: Control log check

**Count: 38 occurrences**

```python
ctrl_log_check(client, [list of expected log entries])
```

**Locations:**

- Lines 384, 390, 405, 430, 467, 484, 497, 514, 527, 544, 557, 570, 590, 612, 630, 650, 708, 733, 753, 816, 887, 947, 1010, 1100, 1126, 1142, 1154, 1214, 1230, 1245, 1261, 1277, 1295, 1313, 1333, 1352, 1425, 1463, 1486, 1544, 1560, 1590, 1636, 1670, 1714, 1734, 1799, 1842, 1879, 1927, 1952, 1992, 2022, 2062, 2096

### Pattern: App log check

**Count: 37 occurrences**

```python
app_log_check(client, [list of expected log messages])
```

**Locations:**

- Lines 391, 406, 431, 468, 498, 528, 659, 736, 754, 817, 888, 956, 1049, 1163, 1369, 1426, 1495, 1598, 1678, 1741, 1886, 1959, 2029, 2063, 2097

### Pattern: Notify slack check

**Count: 29 occurrences**

```python
check_notify_slack(None)  # or check_notify_slack("message")
```

**Locations:**

- Lines 392, 407, 432, 469, 499, 529, 675, 737, 755, 818, 902, 968, 1063, 1179, 1390, 1427, 1509, 1609, 1683, 1752, 1900, 1969, 2030, 2064, 2098

## 5. Time Machine Usage Patterns

### Pattern: Time initialization helpers

**Count: Used throughout tests**

```python
time_morning(offset_min=0)  # Line 103
time_evening(offset_min=0)  # Line 107
time_str(time)             # Line 111
```

These helper functions are used extensively to generate consistent time values.

## Summary of Major Duplication Issues

1. **Sensor Mocking**: The complex pattern of mocking both direct calls and scheduler imports could be extracted into a helper function.

2. **API Call Patterns**: The repetitive client.get() calls with similar query_string structures could be wrapped in helper methods.

3. **Schedule Data Setup**: The pattern of creating and modifying schedule_data is repeated extensively.

4. **Time Movement**: The pattern of move_to() followed by time.sleep() appears over 40 times and could be combined into a single helper.

5. **Assertion Patterns**: The combination of response.status_code and response.json checks could be simplified.

## Recommended Refactoring

1. Create a test helper module with:

    - `mock_sensor_data(mocker, initial_value)`
    - `set_shutter_state(client, state, index=None)`
    - `set_schedule(client, schedule_data)`
    - `advance_time(time_machine, target_time, wait=1)`
    - `assert_api_success(response)`

2. Extract common test scenarios into parameterized tests where similar logic is repeated with different inputs.

3. Create fixture functions for common test setups like sensor mocking patterns.
