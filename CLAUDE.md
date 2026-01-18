# CLAUDE.md

このファイルは、Claude Code（claude.ai/code）がこのリポジトリでコードを扱う際のガイダンスを提供します。

## プロジェクト概要

これは日本の電動シャッター自動化アプリケーション（`rasp-shutter`）で、スケジュールや照度センサーに基づいて電動シャッターを自動制御します。システムはVue.jsフロントエンドとFlaskバックエンドで構成され、ESP32デバイスとREST APIで通信します。

## 重要な注意事項

### コード変更時のドキュメント更新

コードを更新した際は、以下のドキュメントも更新が必要か**必ず検討してください**:

| ドキュメント | 更新が必要なケース                                                 |
| ------------ | ------------------------------------------------------------------ |
| README.md    | 機能追加・変更、使用方法の変更、依存関係の変更                     |
| CLAUDE.md    | アーキテクチャ変更、新規モジュール追加、設定項目変更、開発手順変更 |

### my-lib（共通ライブラリ）の修正について

`my_lib` のソースコードは **`../my-py-lib`** に存在します。

リファクタリング等で `my_lib` の修正が必要な場合:

1. **必ず事前に何を変更したいか説明し、確認を取ること**
2. `../my-py-lib` で修正を行い、commit & push
3. このリポジトリの `pyproject.toml` の my-lib のコミットハッシュを更新
4. `uv lock && uv sync` で依存関係を更新

```bash
# my-lib 更新の流れ
cd ../my-py-lib
# ... 修正 ...
git add . && git commit -m "変更内容" && git push
cd ../rasp-shutter
# pyproject.toml の my-lib ハッシュを更新
uv lock && uv sync
```

### プロジェクト管理ファイルについて

以下のファイルは **`../py-project`** で一元管理しています:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.gitignore`
- `.gitlab-ci.yml`
- その他プロジェクト共通設定

**これらのファイルを直接編集しないでください。**

修正が必要な場合:

1. **必ず事前に何を変更したいか説明し、確認を取ること**
2. `../py-project` のテンプレートを更新
3. このリポジトリに変更を反映

## アーキテクチャ

- **フロントエンド**: Vue 3 with Bootstrap Vue Next、`/rasp-shutter/`ベースパスで提供
- **バックエンド**: モジュラーブループリントを使用したFlaskアプリ（control、schedule、sensor、logging）
- **データ**: ログ用SQLiteデータベース、YAML設定ファイル
- **ハードウェアインターフェース**: ESP32デバイスとのREST API通信
- **デプロイメント**: DockerコンテナとKubernetesサポート

## 主要な開発コマンド

### パッケージ管理

このプロジェクトは**uv**（ryeではない）をPython依存関係管理に使用しています：

```bash
uv sync                  # Python依存関係をインストール
uv sync --upgrade        # 依存関係を最新バージョンにアップグレード
uv run python flask/src/app.py    # Flaskサーバーを直接実行
```

### フロントエンド（Vue.js）

```bash
npm ci                   # 依存関係をインストール
npm run dev             # 開発サーバー
npm run build           # 本番ビルド
npm run lint            # ESLintと自動修正
npm run format          # Prettierフォーマット
```

### バックエンド（Python）

```bash
# 開発モード
uv run python flask/src/app.py -D    # デバッグモード
uv run python flask/src/app.py -d    # ダミーモード（ハードウェアなしでCI/テスト用）
uv run python flask/src/app.py -p 8080    # カスタムポート
```

### テスト

```bash
uv run pytest                        # カバレッジ付きで全テストを実行
uv run pytest tests/test_basic.py    # 特定のテストファイルを実行
uv run pytest tests/test_playwright.py    # E2Eブラウザテスト

# Playwrightテストの場合、Flaskサーバーをダミーモードで起動する必要があります：
DUMMY_MODE=true uv run python flask/src/app.py -d -p 5000 &
uv run pytest tests/test_playwright.py
```

### Docker

```bash
docker compose run --build --rm --publish 5000:5000 rasp-shutter
```

## Flaskアプリケーション構造

Flaskアプリはモジュラーブループリントアーキテクチャを使用しています：

- `rasp_shutter.api.control` - 手動シャッター制御とESP32通信
- `rasp_shutter.api.schedule` - スケジュール管理と自動化ロジック
- `rasp_shutter.api.sensor` - センサーデータ処理（照度、温度）
- `rasp_shutter.api.test.time` - 時間モック用テストAPI（DUMMY_MODEのみ）
- `my_lib.webapp.*` - 共有ライブラリモジュール（ログ、イベント、ユーティリティ）

すべてのルートは`/rasp-shutter`でプレフィックスされます（`my_lib.webapp.config.URL_PREFIX`で設定）。

## 主要コンポーネント

### スケジューラシステム

- `rasp_shutter.scheduler` - 並列テスト実行用のワーカー固有インスタンスを持つコアスケジューリングロジック
- カスタムリトライロジックと明度状態管理を伴うPython `schedule`ライブラリを使用
- 信頼性の高いテスト用のテストAPIを通じた時間モックをサポート

### DUMMY_MODEテスト

- 環境変数`DUMMY_MODE=true`でハードウェアなしでのテストを有効化
- モックESP32エンドポイントと時間操作APIを提供
- Playwrightブラウザ自動化テストに必要

### フロントエンドコンポーネント

- `ManualControl.vue` - 手動シャッター操作インターフェース
- `ScheduleSetting.vue` - スケジュール設定UI
- `SensorData.vue` - リアルタイムセンサー監視
- `AppLog.vue` - 操作履歴表示

## 設定

- メイン設定: `config.yaml` （`config.example.yaml`からコピー）
- スキーマ検証: `config.schema`
- 環境変数`DUMMY_MODE`でテスト/シミュレーションモードを制御

## テスト設定

pytestを使用したテスト：

- HTMLレポートは`tests/evidence/`に生成
- カバレッジレポートは`tests/evidence/coverage/`に生成
- ブラウザ自動化テスト用Playwright（Flaskサーバーの実行が必要）
- 日付/時間モック用time-machine
- 並列実行用のワーカー固有スケジューラインスタンス（pytest-xdist）

## コーディング規約

### Python バージョン

- Python 3.10 以上

### スタイル

- ruff でフォーマット・lint
- pyright で型チェック
- 型ヒントを積極的に使用

### インポートスタイル

`from xxx import yyy` は基本的に使わず、`import xxx` としてモジュールをインポートし、使用時は `xxx.yyy` の形式で参照する。

```python
# 推奨
import my_lib.webapp.config
my_lib.webapp.config.URL_PREFIX

# 非推奨
from my_lib.webapp.config import URL_PREFIX
URL_PREFIX
```

**例外:**

- 標準ライブラリの一般的なパターン（例: `from pathlib import Path`）
- 型ヒント用のインポート（`from typing import TYPE_CHECKING`）
- dataclass などのデコレータ（`from dataclasses import dataclass`）

### 型チェック（pyright）

pyright のエラー対策として、各行に `# type: ignore` コメントを付けて回避するのは**最後の手段**とします。

基本方針:

1. **型推論が効くようにコードを書く** - 明示的な型注釈や適切な変数の初期化で対応
2. **型の絞り込み（Type Narrowing）を活用** - `assert`, `if`, `isinstance()` 等で型を絞り込む
3. **どうしても回避できない場合のみ `# type: ignore`** - その場合は理由をコメントに記載

```python
# 推奨: 型の絞り込み
value = get_optional_value()
assert value is not None
use_value(value)

# 非推奨: type: ignore での回避
value = get_optional_value()
use_value(value)  # type: ignore
```

**例外:** テストコードでは、モックオブジェクトの使用など型チェックが困難な場合に `# type: ignore` を使用可能です。

### 型定義

センサーデータやAPIレスポンスには `rasp_shutter.types` で定義された TypedDict を使用する。

```python
# 推奨
import rasp_shutter.types

def get_sensor_data(config: AppConfig) -> rasp_shutter.types.SensorData:
    ...

# 非推奨
def get_sensor_data(config: AppConfig) -> dict:
    ...
```

### 型比較

型チェックには `isinstance()` を使用する。`type(x) is T` は避ける。

```python
# 推奨
if not isinstance(entry["is_active"], bool):
    return False

# 非推奨
if type(entry["is_active"]) is not bool:
    return False
```

### 文字列フォーマット

f 文字列を優先的に使用する。`.format()` は避ける。

```python
# 推奨
message = f"シャッター{name}を{state}ました。"

# 非推奨
message = "シャッター{name}を{state}ました。".format(name=name, state=state)
```

### ループスタイル

- `range(len(x))` は index のみを使用する場合に限り許容
- index と value の両方を使用する場合は `enumerate()` を使用

```python
# 推奨: index と value の両方を使用
for i, item in enumerate(items):
    result[i] = process(item)

# 許容: index のみを使用
for i in range(len(items)):
    items[i] = None
```

### 条件式

- 不要な括弧は削除する（`if (a) or (b):` → `if a or b:`）
- 三項演算子のネストは避け、辞書マッピングまたは関数を使用

```python
# 推奨: 辞書マッピング
MODE_TO_STR = {
    CONTROL_MODE.MANUAL: "manual",
    CONTROL_MODE.SCHEDULE: "schedule",
    CONTROL_MODE.AUTO: "auto",
}
mode_str = MODE_TO_STR[mode]

# 非推奨: ネストした三項演算子
mode_str = "manual" if mode == CONTROL_MODE.MANUAL else "schedule" if mode == CONTROL_MODE.SCHEDULE else "auto"
```

### 設定値の辞書管理

複数の関連する設定値をまとめる場合は、タプルではなくNamedTupleを使用する。

```python
# 推奨: NamedTupleで意図を明確化
import typing

class ModeConfig(typing.NamedTuple):
    divisor: float
    threshold: float
    description: str

MODE_CONFIG = {
    MODE.A: ModeConfig(60, 5, "手動"),
    MODE.B: ModeConfig(3600, 1, "自動"),
}
config = MODE_CONFIG[mode]
if value / config.divisor < config.threshold:
    ...

# 非推奨: 素のタプルで意図が不明確
MODE_CONFIG = {
    MODE.A: (60, 5, "手動"),
    MODE.B: (3600, 1, "自動"),
}
divisor, threshold, desc = MODE_CONFIG[mode]
```

### 型チェックのループ化

同じパターンの型チェックが繰り返される場合は、辞書とループで統一する。

```python
# 推奨: 辞書ベースのループ
FIELD_TYPES = {"name": str, "count": int, "active": bool}
for field, expected_type in FIELD_TYPES.items():
    if not isinstance(data.get(field), expected_type):
        return False

# 非推奨: 同じパターンの繰り返し
if not isinstance(data["name"], str):
    return False
if not isinstance(data["count"], int):
    return False
if not isinstance(data["active"], bool):
    return False
```

### 共通関数

- 重複するロジックは共通関数化し、`types.py` または適切なモジュールに配置

```python
# 推奨: 共通関数を使用
import rasp_shutter.types
state_text = rasp_shutter.types.state_to_action_text(state)

# 非推奨: 同じロジックを複数箇所に記述
state_text = "開け" if state == "open" else "閉め"
```

### 環境変数チェック

- 環境変数の判定は専用のヘルパー関数を使用する
- 同じ判定ロジックを複数箇所に書かない

```python
# 推奨
import rasp_shutter.util
if rasp_shutter.util.is_dummy_mode():
    ...

# 非推奨
import os
if os.environ.get("DUMMY_MODE", "false") == "true":
    ...
```

### ワーカーID取得

pytest-xdist の並列実行で使用するワーカーID取得には `rasp_shutter.util.get_worker_id()` を使用する。

```python
# 推奨
import rasp_shutter.util
worker_id = rasp_shutter.util.get_worker_id()

# 非推奨
import os
worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
```

### テストAPIのDUMMY_MODEチェック

テスト用APIでのDUMMY_MODEチェックには `@rasp_shutter.util.require_dummy_mode` デコレータを使用する。

```python
# 推奨: デコレータを使用
import rasp_shutter.util

@blueprint.route("/api/test/example", methods=["POST"])
@rasp_shutter.util.require_dummy_mode
def test_example():
    # DUMMY_MODEチェック不要、直接ロジックを記述
    return {"success": True}

# 非推奨: インラインでの判定
@blueprint.route("/api/test/example", methods=["POST"])
def test_example():
    error = rasp_shutter.util.check_dummy_mode_for_api()
    if error:
        return error
    return {"success": True}
```

### テスト環境判定

pytest実行中かどうかの判定には `rasp_shutter.util.is_pytest_running()` を使用する。

```python
# 推奨
import rasp_shutter.util
if rasp_shutter.util.is_pytest_running():
    ...

# 非推奨
import os
if os.environ.get("PYTEST_CURRENT_TEST"):
    ...
```

### 定数管理

- 時間に関する定数は `control/config.py` に集約する
- マジックナンバーは避け、意味のある定数名を使用する

```python
# 推奨
import rasp_shutter.control.config
if hour > rasp_shutter.control.config.HOUR_MORNING_START:
    ...

# 非推奨
if hour > 5:
    ...
```

### 正規表現パターン

繰り返し使用する正規表現パターンは、モジュールレベルでコンパイル済み定数として定義する。

```python
# 推奨: コンパイル済みパターンを定数として定義
SCHEDULE_TIME_PATTERN = re.compile(r"\d{2}:\d{2}")

def validate_time(time_str: str) -> bool:
    return bool(SCHEDULE_TIME_PATTERN.search(time_str))

# 非推奨: 毎回コンパイル
def validate_time(time_str: str) -> bool:
    return bool(re.compile(r"\d{2}:\d{2}").search(time_str))
```

### type: ignore の使用

`# type: ignore` を使用する場合は、必ず理由をコメントで記載する。

```python
# 推奨: 理由を記載
# functools.wraps で型情報が保持されないため
return decorated_function  # type: ignore[return-value]

# 非推奨: 理由なし
return decorated_function  # type: ignore
```

### パス管理

- ファイルパスの構築は専用関数を使用する
- テンプレート文字列 + format() の2段階処理は避ける

```python
# 推奨
import rasp_shutter.control.config
path = rasp_shutter.control.config.get_exec_stat_path(state, index)

# 非推奨
import pathlib
path = pathlib.Path(str(TEMPLATE[state]).format(index=index))
```

### タイムゾーン

- タイムゾーン処理は `my_lib.time` APIを使用する
- `pytz.timezone()` の直接呼び出しは避ける
- 外部ライブラリがUTC時刻を要求する場合は、コメントで理由を明記する

```python
# 推奨
import my_lib.time
tz = my_lib.time.get_zoneinfo()
now = my_lib.time.now()

# 非推奨
import pytz
tz = pytz.timezone("Asia/Tokyo")

# UTC時刻が必要な場合はコメントで理由を明記
# pysolar.solar.get_altitude() はUTC時刻を要求するため、明示的にUTCを使用
now = datetime.datetime.now(datetime.UTC)
```

## リファクタリング調査の方針

コードのリファクタリング機会を評価する際は、以下の観点で調査を行い、**メリットがデメリットを上回る場合のみ**実施する。

### 調査観点

1. **Protocol等を使った型整備**
    - `| None` の多用箇所で、型の絞り込みで削減可能か
    - `isinstance()` の多用箇所で、Protocolで統一可能か
    - 同じインターフェースを持つ複数クラスの共通化

2. **dict/TypedDict の dataclass 化**
    - 辞書キーアクセスが頻繁で typo リスクがある箇所
    - 不変性が必要な設定データ
    - ただし、JSONシリアライズが容易なTypedDictが適切な場合もある

3. **コーディングパターンの統一**
    - 同じ機能を異なる方法で実装している箇所
    - エラーハンドリング、ログ出力、環境変数チェック等

4. **my_lib 機能の活用**
    - タイムゾーン処理: `my_lib.time` を使用
    - ファイルI/O: `my_lib.serializer` を使用
    - SQLite接続: `my_lib.sqlite_util` を使用
    - タイムスタンプファイル: `my_lib.footprint` を使用

5. **パス管理**
    - `pathlib.Path` を使用（文字列パスは避ける）
    - `my_lib.webapp.config` の base_dir を活用
    - ハードコーディングされたパスは設定に移動

### 見送り基準

以下の場合は改善を見送る：

- 影響範囲が広く、既存の安定動作を損なうリスクがある
- 実装コストが効果に見合わない
- 過度な抽象化でかえって複雑になる
- 外部ライブラリの仕様に依存している
