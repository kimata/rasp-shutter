# 🏠 rasp-shutter

Raspberry Pi を使った電動シャッター自動制御システム

[![Regression](https://github.com/kimata/rasp-shutter/actions/workflows/regression.yaml/badge.svg)](https://github.com/kimata/rasp-shutter/actions/workflows/regression.yaml)

## 📚 目次

- [📋 概要](#-概要)
    - [主な特徴](#主な特徴)
- [🖼️ スクリーンショット](#️-スクリーンショット)
- [🎮 デモ](#-デモ)
- [🏗️ システム構成](#️-システム構成)
    - [フロントエンド](#フロントエンド)
    - [バックエンド](#バックエンド)
    - [ハードウェア](#ハードウェア)
- [🚀 セットアップ](#-セットアップ)
    - [必要な環境](#必要な環境)
    - [1. 依存パッケージのインストール](#1-依存パッケージのインストール)
    - [2. 設定ファイルの準備](#2-設定ファイルの準備)
- [💻 実行方法](#-実行方法)
    - [Docker を使用する場合（推奨）](#docker-を使用する場合推奨)
    - [Docker を使用しない場合](#docker-を使用しない場合)
    - [開発モード](#開発モード)
- [🧪 テスト](#-テスト)
- [🎯 API エンドポイント](#-api-エンドポイント)
    - [シャッター制御](#シャッター制御)
    - [スケジュール管理](#スケジュール管理)
    - [センサー情報](#センサー情報)
    - [ログ・履歴](#ログ履歴)
- [📈 メトリクス機能](#-メトリクス機能)
- [☸️ Kubernetes デプロイ](#️-kubernetes-デプロイ)
- [🔧 カスタマイズ](#-カスタマイズ)
    - [シャッター制御のカスタマイズ](#シャッター制御のカスタマイズ)
    - [フロントエンドのカスタマイズ](#フロントエンドのカスタマイズ)
- [📊 CI/CD](#-cicd)
- [📝 ライセンス](#-ライセンス)

## 📋 概要

電動シャッターをスマートフォンやPCから遠隔操作し、スケジュール機能と光センサーによる完全自動化を実現するシステムです。ESP32を介して電動シャッターを制御します。

### 主な特徴

- 🏠 **リモート制御** - スマホやPCからシャッターの開閉操作
- ⏰ **スケジュール機能** - 時間指定での自動開閉
- ☀️ **光センサー連動** - 屋外の明るさに応じた自動制御
- 📊 **履歴管理** - 操作履歴の保存と確認
- 📱 **レスポンシブUI** - モバイルフレンドリーなWebインターフェース
- 🌡️ **センサー情報表示** - 温度・湿度・照度の監視
- 📈 **メトリクス機能** - センサーデータの時系列グラフ表示とパーマリンク共有

## 🖼️ スクリーンショット

![システム構成](./img/システム構成.png)

## 🎮 デモ

実際の動作を体験できるデモサイト：

🔗 https://rasp-shutter-demo.kubernetes.green-rabbit.net/rasp-shutter/

## 🏗️ システム構成

### フロントエンド

- **フレームワーク**: Vue.js 3
- **UIライブラリ**: Bootstrap Vue Next
- **アイコン**: FontAwesome
- **チャート**: Chart.js

### バックエンド

- **フレームワーク**: Flask (Python)
- **REST API**: ESP32デバイスとの通信
- **データベース**: SQLite
- **タスクスケジューラ**: Python schedule

### ハードウェア

- **制御**: Raspberry Pi + ESP32
- **電動シャッター**: ESP32制御モジュール
- **センサー**: 光センサー（明るさ検知用）
- **詳細**: [ハードウェア構成の詳細はブログ参照](https://rabbit-note.com/2019/03/17/shutter-automation/)

## 🚀 セットアップ

### 必要な環境

- Raspberry Pi または Linux環境
- Python 3.10+
- Node.js 22.x
- Docker (オプション)

### 1. 依存パッケージのインストール

```bash
# システムパッケージ
sudo apt install npm docker

# プロジェクトの依存関係
npm ci
```

### 2. 設定ファイルの準備

```bash
cp config.example.yaml config.yaml
# config.yaml を環境に合わせて編集
```

設定項目の例：

- ESP32デバイスのIPアドレス
- シャッター制御のパラメータ
- センサーのしきい値
- ログ設定

## 💻 実行方法

### Docker を使用する場合（推奨）

```bash
# フロントエンドのビルド
npm ci
npm run build

# Docker Composeで起動
docker compose run --build --rm --publish 5000:5000 rasp-shutter
```

### Docker を使用しない場合

#### uv を使用（推奨）

```bash
# uvのインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストールと実行
uv sync
uv run python flask/src/app.py
```

### 開発モード

```bash
# フロントエンド開発サーバー
npm run dev

# バックエンド（デバッグモード）
uv run python flask/src/app.py -D

# ダミーモード（ハードウェアなしでテスト）
uv run python flask/src/app.py -d
```

## 🧪 テスト

```bash
# Pythonテスト（カバレッジ付き）
uv run pytest

# 特定のテストファイルを実行
uv run pytest tests/test_basic.py

# E2Eテスト（Playwright）
uv run pytest tests/test_playwright.py
```

テスト結果：

- HTMLレポート: `tests/evidence/index.htm`
- カバレッジ: `tests/evidence/coverage/`
- E2E録画: `tests/evidence/test_*/`

## 🎯 API エンドポイント

### シャッター制御

- `GET /api/shutter_ctrl` - シャッター状態取得
- `POST /api/shutter_ctrl` - シャッター開閉制御

### スケジュール管理

- `GET /api/schedule_ctrl` - スケジュール一覧取得
- `POST /api/schedule_ctrl` - スケジュール追加/更新
- `DELETE /api/schedule_ctrl/<id>` - スケジュール削除

### センサー情報

- `GET /api/sensor_data` - センサーデータ取得

### ログ・履歴

- `GET /api/log` - 操作履歴取得

## 📈 メトリクス機能

シャッター操作時のセンサーデータと統計情報の詳細な分析・可視化機能を提供します。

### 収集データ

- **照度（lux）** - 屋外の照度センサーからの値（LUX単位）
- **日射量（solar_rad）** - 太陽の日射量（W/m²単位）
- **太陽高度（altitude）** - 緯度・経度・時刻から計算される太陽高度（度単位）
- **操作履歴** - 手動/自動/スケジュール操作の記録

### 主な機能

- **📊 操作統計グラフ** - 基本統計、時刻分析、時系列データの可視化
- **🔗 パーマリンク機能** - 各グラフセクションへの直接リンク共有
- **📈 センサーデータ分析** - 自動操作時と手動操作時のセンサー値比較
- **📅 過去30日間の統計** - 日次・週次・月次での操作パターン分析

### 利用方法

1. **メトリクスページへアクセス**
   `/rasp-shutter/api/metrics` でメトリクスダッシュボードを表示

2. **パーマリンクの生成**
   各セクション見出しの「🔗」アイコンをクリックしてURLをクリップボードにコピー

### API エンドポイント

- `GET /rasp-shutter/api/sensor` - リアルタイムセンサーデータ取得
- `GET /rasp-shutter/api/metrics` - メトリクスダッシュボードページ表示

### データソース設定

#### InfluxDB（センサーデータ）

```yaml
sensor:
    influxdb:
        url: http://proxy.green-rabbit.net:8086
        token: (トークン)
        org: home
        bucket: sensor
    lux:
        name: 屋外の照度
        measure: sensor.rasp
        hostname: rasp-weather-1
    solar_rad:
        name: 太陽の日射量
        measure: sensor.rasp
        hostname: rasp-weather-1
```

#### SQLite（メトリクスデータ）

```yaml
metrics:
    data: flask/data/metrics.db
```

#### 位置情報（太陽高度計算用）

```yaml
location:
    latitude: 35.6895
    longitude: 139.6917
```

## ☸️ Kubernetes デプロイ

Kubernetes用の設定ファイルが含まれています：

```bash
kubectl apply -f kubernetes/rasp-shutter.yaml
```

CronJobを使った定期実行にも対応しています。詳細は設定ファイルをカスタマイズしてご利用ください。

## 🔧 カスタマイズ

### シャッター制御のカスタマイズ

シャッター制御ロジックは `flask/src/rasp_shutter/` 配下で実装されています。異なるハードウェア構成やプロトコルに対応する場合は、これらのモジュールを修正してください。

### フロントエンドのカスタマイズ

- コンポーネント: `src/` 配下
- スタイル: 各コンポーネントの `.vue` ファイル
- 設定: `vite.config.ts`

## 📊 CI/CD

GitHub Actions によるCI/CDパイプライン：

- テスト結果: https://kimata.github.io/rasp-shutter/
- カバレッジレポート: https://kimata.github.io/rasp-shutter/coverage/

## 📝 ライセンス

このプロジェクトは Apache License Version 2.0 のもとで公開されています。

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://github.com/kimata/rasp-shutter/issues) | [💡 Feature Request](https://github.com/kimata/rasp-shutter/issues/new?template=feature_request.md) | [📖 Wiki](https://github.com/kimata/rasp-shutter/wiki)

</div>
