# CLAUDE.md

このファイルは、Claude Code（claude.ai/code）がこのリポジトリでコードを扱う際のガイダンスを提供します。

## プロジェクト概要

これは日本の電動シャッター自動化アプリケーション（`rasp-shutter`）で、スケジュールや照度センサーに基づいて電動シャッターを自動制御します。システムはVue.jsフロントエンドとFlaskバックエンドで構成され、ESP32デバイスとREST APIで通信します。

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
