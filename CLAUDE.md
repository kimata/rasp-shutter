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
