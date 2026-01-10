from dataclasses import dataclass, field
import numpy as np
from typing import List, Optional
from datetime import datetime

@dataclass
class VideoMetadata:
    """
    Metadata for a video file.
    """
    path: str  # S3 Key
    size: int  # File size in bytes
    last_modified: datetime
    duration: Optional[float] = None  # Duration in seconds, may be None until processed
    
@dataclass
class VideoFingerprint:
    """
    Fingerprint data for a video, containing time-series perceptual hashes.
    """
    metadata: VideoMetadata
    
    # Time-series hashes: Each element is a 64-bit integer representing a frame's pHash
    # We use uint64 for efficient storage and Hamming distance calculation via XOR
    phashes: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.uint64))
    
    # Corresponding timestamps for each hash (in seconds)
    timestamps: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))

    def __repr__(self):
        return f"<VideoFingerprint path={self.metadata.path} frames={len(self.phashes)}>"

    @property
    def frame_count(self) -> int:
        return len(self.phashes)
