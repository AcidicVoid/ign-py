import sys

try:
    import numpy as np
except ImportError:
    print("Error: Required package not installed.")
    print("Please run: pip install numpy")
    sys.exit(1)

def generate_ign_noise(width, height, scale=1, seed=0):
    """
    Generate Interleaved Gradient Noise pattern.
    
    Based on Jorge Jimenez's formula from "Next Generation Post Processing in Call of Duty"
    Formula: frac(52.9829189 * frac(0.06711056 * x + 0.00583715 * y))
    
    Args:
        width: Width of the noise texture
        height: Height of the noise texture
        scale: Scale factor for the noise pattern (default: 1)
        seed: Offset for noise coordinates to vary the pattern (default: 0)
    
    Returns:
        numpy array with values in range [0, 1]
    """
    if seed == -1:
        seed = np.random.randint(0,1000)

    # Create coordinate grids with seed offset
    x = np.arange(width).reshape(1, -1) + seed
    y = np.arange(height).reshape(-1, 1) + seed
    
    # Apply IGN formula with scale
    x_scaled = x / scale
    y_scaled = y / scale
    
    f = 0.06711056 * x_scaled + 0.00583715 * y_scaled
    noise = np.modf(52.9829189 * np.modf(f)[0])[0]
    
    return noise