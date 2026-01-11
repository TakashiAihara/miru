# Miru - Video Similarity Detection System

高速な動画類似性検出システム。S3互換ストレージ上の大量の動画から、重複・類似・切り抜き動画を検出します。

## 特徴

- ✅ **高速**: Perceptual Hash (pHash) による効率的な類似性判定
- ✅ **柔軟**: エンコード違い、解像度変更、時間的な切り抜きに対応
- ✅ **汎用**: Wasabi, AWS S3, MinIO, Cloudflare R2 など S3互換ストレージに対応
- ✅ **スケーラブル**: 数千〜数万件の動画を処理可能

## 検出できるもの

- ✅ エンコード違い（解像度変更、再圧縮、色調補正）
- ✅ 時間的な切り抜き（元動画の一部分を抜き出したクリップ）
- ✅ ほぼ同一の動画（わずかなノイズや画質劣化）

## セットアップ

### 1. 必要なツール

- Python 3.14+
- FFmpeg
- S3互換ストレージのアクセスキー

### 2. インストール

```bash
# リポジトリをクローン
git clone https://github.com/TakashiAihara/miru.git
cd miru

# 仮想環境の作成（mise使用の場合）
mise install
mise exec -- uv venv
mise exec -- uv pip install -r requirements.txt

# または標準のvenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
# .env.example をコピー
cp .env.example .env

# .env を編集して実際の認証情報を入力
```

#### Wasabi の場合

```env
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
S3_ENDPOINT_URL=https://s3.ap-northeast-2.wasabisys.com
S3_REGION=ap-northeast-2
```

#### AWS S3 の場合

```env
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket_name
S3_ENDPOINT_URL=https://s3.us-east-1.amazonaws.com
S3_REGION=us-east-1
```

#### MinIO の場合

```env
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=videos
S3_ENDPOINT_URL=http://localhost:9000
S3_REGION=us-east-1
```

## 使い方

### 1. 接続テスト

```bash
python scripts/test_connection.py
```

### 2. 動画のインデックス化

#### シングルプロセス版 (テスト用)

```bash
python scripts/run_indexer.py
```

#### 並列処理版 (本番用・推奨)

```bash
# 全CPUコアを使用して高速処理
python scripts/run_parallel_indexer.py
```

**処理時間の目安**:
- シングルプロセス: 30,000件 → 約33時間
- 並列処理 (16コア): 30,000件 → 約8時間

これにより:
1. S3バケット内の全動画をスキャン
2. 各動画のフィンガープリント（pHash）を生成
3. SQLiteデータベースに保存

### 3. 類似動画の検索

```bash
# TODO: 実装予定
python scripts/find_duplicates.py
```

## アーキテクチャ

```
miru/
├── miru/
│   ├── models.py       # データモデル
│   ├── fingerprint.py  # pHash生成
│   ├── algo.py         # 類似性判定アルゴリズム
│   ├── indexer.py      # バッチ処理
│   └── storage.py      # DB管理
├── scripts/
│   ├── test_connection.py
│   └── run_indexer.py
├── data/
│   ├── fingerprints/   # 生成されたハッシュデータ
│   └── temp/           # 一時ファイル
└── miru.db             # SQLiteデータベース
```

## パフォーマンス

- **フィンガープリント生成**: 約4秒/動画（30秒分）
- **検索**: TODO

## 今後の改善予定

- [ ] 並列処理による高速化
- [ ] Vector Database (Qdrant) 導入
- [ ] レポート生成機能
- [ ] Web UI

## ライセンス

MIT

## 貢献

Issue や Pull Request を歓迎します。
