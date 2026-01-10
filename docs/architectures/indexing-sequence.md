# インデックス処理シーケンス

## 処理フロー

```mermaid
sequenceDiagram
    participant User
    participant Indexer
    participant S3
    participant DB
    participant FFmpeg
    participant pHash
    participant FileSystem

    User->>Indexer: run_indexer.py 実行
    
    Note over Indexer,S3: Phase 1: バケットスキャン
    Indexer->>S3: list_objects_v2()
    S3-->>Indexer: ファイルリスト (1492件)
    
    loop 各ファイル
        Indexer->>DB: add_or_update_video()
        DB-->>Indexer: video_id
    end
    
    Note over Indexer,FileSystem: Phase 2: フィンガープリント生成
    Indexer->>DB: get_unprocessed_videos(limit=5)
    DB-->>Indexer: 未処理動画リスト
    
    loop 各動画 (5件)
        Indexer->>S3: download_file()
        S3-->>Indexer: 動画データ
        Indexer->>FileSystem: 一時保存 (data/temp/)
        
        Indexer->>FFmpeg: generate_fingerprints(local_path, max_duration=30)
        
        Note over FFmpeg,pHash: フレーム抽出 & ハッシュ計算
        FFmpeg->>FFmpeg: デコード (1fps, 144x144)
        loop 30フレーム
            FFmpeg->>pHash: フレーム画像
            pHash->>pHash: pHash計算 (64bit)
            pHash-->>FFmpeg: ハッシュ値
        end
        
        FFmpeg-->>Indexer: timestamps[], hashes[]
        
        Indexer->>FileSystem: save fingerprint (.npz)
        Indexer->>DB: mark_processed()
        Indexer->>FileSystem: 一時ファイル削除
    end
    
    Indexer-->>User: 処理完了
```

## 処理時間

| フェーズ | 処理時間 | 備考 |
|---------|---------|------|
| バケットスキャン | ~30秒 | 1492件の場合 |
| 1動画あたりの処理 | ~4秒 | 30秒分のフィンガープリント生成 |
| 5動画の処理 | ~20秒 | 並列化で高速化可能 |

## データ保存形式

### SQLite (miru.db)

```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY,
    s3_key TEXT UNIQUE,
    size INTEGER,
    last_modified TEXT,
    duration REAL,
    processed_at TEXT,
    fingerprint_path TEXT
);
```

### Fingerprint Files (.npz)

```python
{
    'timestamps': np.array([0.0, 1.0, 2.0, ..., 29.0], dtype=float32),
    'hashes': np.array([0x1a2b3c4d5e6f7890, ...], dtype=uint64)
}
```
