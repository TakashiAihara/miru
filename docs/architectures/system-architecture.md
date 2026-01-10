# システムアーキテクチャ

## 概要

Miruは、S3互換ストレージ上の大量の動画から重複・類似・切り抜き動画を検出するシステムです。

## コンポーネント構成

```mermaid
graph TB
    subgraph "Storage Layer"
        S3[S3-Compatible Storage<br/>Wasabi/AWS S3/MinIO]
    end
    
    subgraph "Processing Layer"
        Indexer[Indexer<br/>バッチ処理]
        Fingerprint[Fingerprint Generator<br/>pHash計算]
        Search[Search Engine<br/>類似性判定]
    end
    
    subgraph "Data Layer"
        DB[(SQLite Database<br/>メタデータ)]
        FP[Fingerprint Files<br/>.npz]
    end
    
    subgraph "Interface Layer"
        CLI[CLI Scripts]
    end
    
    S3 --> Indexer
    Indexer --> Fingerprint
    Fingerprint --> FP
    Indexer --> DB
    DB --> Search
    FP --> Search
    CLI --> Indexer
    CLI --> Search
```

## データフロー

```mermaid
flowchart LR
    A[動画ファイル] --> B[S3 Storage]
    B --> C[Indexer]
    C --> D[FFmpeg Decoder]
    D --> E[Frame Extraction]
    E --> F[pHash Calculation]
    F --> G[Fingerprint DB]
    G --> H[Similarity Search]
    H --> I[レポート出力]
```

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| 言語 | Python 3.14 |
| ストレージ | S3-Compatible (boto3) |
| 動画処理 | FFmpeg, opencv-python |
| ハッシュ計算 | imagehash (pHash) |
| データベース | SQLite |
| 数値計算 | NumPy, SciPy |
| 検索アルゴリズム | カスタム実装（ハミング距離ベース） |
