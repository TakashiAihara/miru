import numpy as np
from typing import Tuple, List

def bit_count_np(arr: np.ndarray) -> np.ndarray:
    """
    Counts set bits in a numpy array of integers.
    Works by viewing as uint8 and using a lookup table or simply unpacking.
    For 64-bit hashes, viewing as uint8 and summing is efficient enough.
    """
    # View as 8 separate bytes
    # Little-endian vs Big-endian doesn't matter for bit count
    bytes_view = arr.view(np.uint8)
    
    # Simple lookup table for 8-bit population count
    # ranges from 0 to 255
    # There are faster bit-twiddling hacks, but this is vectorizable in pure numpy easily.
    # Or use verify specific library. 
    # For now, let's use the slow but sure unpackbits for clarity, or a simple bit hack loop.
    
    # Actually, np.unpackbits only works on uint8.
    unpacked = np.unpackbits(bytes_view)
    # unpacked is 1D array of bits. We need to reshape to (N, 64) or similar to sum.
    # original arr shape: (N,) -> bytes_view: (N*8,) -> unpacked: (N*64,)
    
    # Reshape to conserve the structure
    # Note: bit_count for a scalar is simple, for array we sum.
    
    # Let's use a standard trick for population count on uint64 if performance is critical later.
    # For now: unpackbits approach.
    return unpacked.reshape(arr.shape + (64,)).sum(axis=-1)

def calculate_sequence_similarity(
    hashes_a: np.ndarray, 
    hashes_b: np.ndarray, 
    threshold: int = 5
) -> float:
    """
    Calculates similarity between two sequences of hashes.
    Checks if sequence A is contained in B (or vice versa) or if they overlap.
    
    For exact duplications or near-duplications, we expect high element-wise similarity.
    
    Strategy:
    1. Assume roughly same frame rate.
    2. Try to align them with minimum distance.
    """
    # Placeholder for complex alignment logic.
    # For now, simple minimum average hamming distance.
    pass

def find_subsequence_match(
    haystack: np.ndarray, 
    needle: np.ndarray, 
    threshold: float = 10.0
) -> Tuple[bool, int, float]:
    """
    Scans 'haystack' (long video) to find where 'needle' (short video) fits best.
    
    Returns:
        (found, start_index_in_haystack, average_distance)
    """
    n_needle = len(needle)
    n_haystack = len(haystack)
    
    if n_needle > n_haystack:
        return False, -1, 999.0
        
    # Naive sliding window for MVP
    # Can be optimized with FFT or other signal processing techniques later.
    
    min_dist = float('inf')
    best_idx = -1
    
    # Vectorized sliding window is hard with pure numpy for Hamming distance 
    # without broadcasting a huge matrix (N-M) x M.
    # If M is small (e.g. 100 frames), it's fine.
    
    # Let's try broadcasting for small needles.
    if n_needle < 1000:
        # Create a view of sliding windows
        # shape: (n_haystack - n_needle + 1, n_needle)
        strides = haystack.strides[0]
        windows = np.lib.stride_tricks.as_strided(
            haystack, 
            shape=(n_haystack - n_needle + 1, n_needle), 
            strides=(strides, strides)
        )
        
        # XOR with needle
        # needle shape: (n_needle,)
        # xor result shape: (num_windows, n_needle)
        xor_matrix = np.bitwise_xor(windows, needle)
        
        # Count bits.
        # This is the heavy part. 
        # Convert to uint8 view -> unpackbits is too slow for 2D large array?
        # Let's map a simple bit_count function or use a rough approximation (numerical difference) 
        # No, numerical diff is useless for hashes.
        
        # Optimization: sum of popcounts.
        # We can just define a ufunc or use a trick.
        # Let's use the primitive: (x & 0x5555...) + ((x >> 1) & 0x5555...)
        
        def popcount_uint64(x):
            x = (x & 0x5555555555555555) + ((x >> 1) & 0x5555555555555555)
            x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
            x = (x & 0x0f0f0f0f0f0f0f0f) + ((x >> 4) & 0x0f0f0f0f0f0f0f0f)
            x = (x & 0x00ff00ff00ff00ff) + ((x >> 8) & 0x00ff00ff00ff00ff)
            x = (x & 0x0000ffff0000ffff) + ((x >> 16) & 0x0000ffff0000ffff)
            x = (x & 0x00000000ffffffff) + ((x >> 32) & 0x00000000ffffffff)
            return x

        # This popcount is element-wise
        # We can implement this in numpy using bitwise operations
        x = xor_matrix
        x = (x & 0x5555555555555555) + ((x >> 1) & 0x5555555555555555)
        x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
        x = (x & 0x0f0f0f0f0f0f0f0f) + ((x >> 4) & 0x0f0f0f0f0f0f0f0f)
        x = (x & 0x00ff00ff00ff00ff) + ((x >> 8) & 0x00ff00ff00ff00ff)
        x = (x & 0x0000ffff0000ffff) + ((x >> 16) & 0x0000ffff0000ffff)
        # Final step can be summed directly
        x = (x & 0x00000000ffffffff) + ((x >> 32) & 0x00000000ffffffff)
        
        # Now x contains the popcount for each element
        # Sum across rows (axis 1) to get total distance for each window
        window_distances = x.sum(axis=1)
        
        # Find minimum
        best_idx = np.argmin(window_distances)
        min_dist = window_distances[best_idx] / n_needle # Average distance per frame
        
        return min_dist < threshold, int(best_idx), float(min_dist)

    else:
        # Fallback for very large needles: iterate?
        # Or just use the same method but chunked.
        # For now, assume needles are clips (< a few minutes).
        return False, -1, 999.0
