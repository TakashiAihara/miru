# Video Similarity Detection System Design - Miru

## 1. 概要 (Overview)

Wasabi上の大量の動画データ（約2.8TB, 数万ファイル）から、重複および類似動画
（エンコード違い、部分的な切り抜きを含む）を高速に検出するシステムの設計書です。

## 2. 検出戦略 (Detection Strategy)

パフォーマンスを最優先しつつ、「切り抜き」や「エンコード差異」に対応するため、
マルチステージの比較パイプラインを採用します。

### Level 1: メタデータ & 完全一致 (Fast Filter)

* **手法**: ファイルサイズ、Duration（再生時間）による大まかな分類。
* **目的**: 計算コストをかけずに、明らかに異なるものを比較対象から外す。

### Level 2: Perceptual Hashing (視覚的ハッシュ)

これが本システムの核となります。

* **手法**: 動画から一定間隔（例: 2秒ごと）でフレームをサンプリングし、
  各フレームの **pHash (Perceptual Hash)** または
  **dHash (Difference Hash)** を計算します。
* **特徴**:
  * **エンコード耐性**: 解像度の変更、再圧縮、色調の微細な変化があっても、
    ハッシュ値は非常に近い値になります（ハミング距離が小さい）。
  * **高速性**: Deep Learningモデルと比較して計算コストが圧倒的に低いです。
* **データ構造**:
  1つの動画を「64bit整数の配列 (Time Series Fingerprints)」として表現します。

### Level 3: 部分一致検索 (Temporal Partial Matching)

* **課題**: 「切り抜き動画」は、全体の平均ハッシュでは検出できません。
* **解決策**:
  * 動画A（短い）のハッシュ配列が、動画B（長い）のハッシュ配列の部分列として、
    ある閾値以内の誤差で存在するかを探索します。
  * Alignmentアルゴリズム（配列のズレ補正）を用いて、
    フレームレートの違いや微妙な編集点に対応します。

## 3. システムアーキテクチャ (Architecture)

### 技術スタック (Tech Stack)

* **Language**: Python 3.10+ (エコシステムとパフォーマンスのバランス)
* **Storage Access**: `boto3` (Wasabi/S3操作)
* **Video Engine**:
  `ffmpeg-python` / `opencv-python-headless` (デコード処理)
* **Math/Algorithm**:
  `numpy`, `scikit-learn` (行列演算、KD-Tree/Ball-Tree探索)
* **Database**: `SQLite` (メタデータ管理),
  `Numpy Memory Map` (特徴量データ) -
  数万件規模ならRDBMSよりファイルベースの配列操作の方が高速な場合があります。

### 処理フロー (Workflow)

1. **Inventory Scan**:
    * Wasabiバケットをスキャンし、全ファイルリスト（Key, Size, Timestamp）をDBに保存。
2. **Fingerprinting (並列処理)**:
    * WorkerプロセスがS3から動画をストリーム読み込み
      （可能な限りローカル保存せずメモリ上で処理）。
    * フレームをデコード -> pHash計算 -> 配列として保存。
    * 結果を「フィンガープリントDB」に格納。
3. **Similarity Analysis (行列演算フェーズ)**:
    * **重複検出**: 全動画の代表ハッシュ（単純平均などへ軽量化したもの）で近傍検索。
    * **切り抜き検出**: 候補となったペアについて、詳細な時系列ハッシュ比較を実行。
4. **Reporting**:
    * 検出されたペア（Original, Duplicate/Clip, Confidence Score）をレポート出力。

## 4. パフォーマンス戦略

* **S3 Read Optimization**: 動画全体をダウンロードするのではなく、
  必要なフレーム周辺のみを読み込む、
  あるいは `ffmpeg` のストリーミング機能を活用してネットワーク帯域を節約します。
* **Vectorization**: Pythonのループを使わず、
  `numpy` のブロードキャスト機能を活用して、
  何万ものハッシュ比較を一括で行います。

## 5. 検討事項 (Constraints)

* **時間的な切り抜き（Temporal Segments）への対応**:
  「ある動画の一部を時間的に切り抜いた動画」の検出に特化します。
  画面全体を使用している前提であれば、pHashの時系列マッチングで
  非常に高い精度とパフォーマンスを両立可能です。
  （画面の一部分だけを切り取る空間的なクロッピングは今回は対象外とします）
