# フィンガープリント生成プロセス

## 処理フロー

```mermaid
flowchart TD
    A[動画ファイル] --> B{FFmpeg Probe}
    B --> C[メタデータ取得<br/>width, height, duration]
    C --> D[FFmpeg Pipeline 構築]
    
    D --> E[入力設定<br/>-t 30秒制限]
    E --> F[FPS フィルタ<br/>1fps]
    F --> G[スケールフィルタ<br/>144x144]
    G --> H[出力設定<br/>rawvideo, rgb24]
    
    H --> I[非同期実行<br/>pipe_stdout=True]
    
    I --> J{フレーム読み込みループ}
    J --> K[144x144x3 bytes 読み込み]
    K --> L[PIL Image 変換]
    L --> M[pHash 計算<br/>8x8 = 64bit]
    M --> N[uint64 に変換]
    N --> O[配列に追加]
    
    O --> P{max_duration 到達?}
    P -->|No| J
    P -->|Yes| Q[プロセス終了待機]
    
    Q --> R[NumPy 配列に変換]
    R --> S[timestamps, hashes 返却]
```

## pHash 計算詳細

```mermaid
flowchart LR
    A[RGB Image<br/>144x144] --> B[グレースケール変換]
    B --> C[DCT変換<br/>Discrete Cosine Transform]
    C --> D[低周波成分抽出<br/>8x8]
    D --> E[中央値計算]
    E --> F[2値化<br/>> median = 1]
    F --> G[64bit ハッシュ値]
```

## ハッシュの特性

### エンコード耐性

| 変更内容 | ハミング距離 | 検出可能性 |
|---------|-------------|-----------|
| 解像度変更 (1080p→720p) | 0-5 | ✅ 高 |
| 再圧縮 (H.264→H.265) | 0-8 | ✅ 高 |
| 色調補正 | 3-10 | ✅ 中 |
| クロッピング (空間) | 20+ | ❌ 低 |
| シーン編集 | 30+ | ❌ 不可 |

### パフォーマンス

```python
# 1フレームあたりの処理時間
- FFmpeg デコード: ~50ms
- pHash 計算: ~10ms
- 合計: ~60ms/frame

# 30秒動画 (30フレーム @ 1fps)
- 理論値: 30 * 60ms = 1.8秒
- 実測値: ~4秒 (ネットワーク・I/O含む)
```

## コード例

```python
# miru/fingerprint.py の核心部分
def generate_fingerprints(file_path, fps=1.0, max_duration=30.0):
    # FFmpeg パイプライン
    input_stream = ffmpeg.input(file_path, t=max_duration)
    process = (
        input_stream
        .filter('fps', fps=fps)
        .filter('scale', 144, 144)
        .output('pipe:', format='rawvideo', pix_fmt='rgb24')
        .run_async(pipe_stdout=True)
    )
    
    # フレーム処理ループ
    hashes = []
    timestamps = []
    frame_idx = 0
    
    while True:
        in_bytes = process.stdout.read(144 * 144 * 3)
        if not in_bytes:
            break
            
        image = Image.frombytes('RGB', (144, 144), in_bytes)
        h = imagehash.phash(image, hash_size=8)
        hash_val = int(str(h), 16)  # 64bit整数に変換
        
        hashes.append(hash_val)
        timestamps.append(frame_idx / fps)
        frame_idx += 1
    
    return np.array(timestamps), np.array(hashes, dtype=np.uint64)
```
