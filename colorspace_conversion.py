import sys

try:
    import numpy as np
except ImportError:
    print("Error: Required package not installed.")
    print("Please run: pip install numpy")
    sys.exit(1)

def rgb_to_lab(rgb):
    """
    Convert RGB to LAB color space.
    
    Args:
        rgb: numpy array in range [0, 255] with shape (height, width, 3)
    
    Returns:
        numpy array in LAB color space
    """
    # Normalize RGB to [0, 1]
    rgb = rgb / 255.0
    
    # Apply gamma correction (sRGB to linear RGB)
    mask = rgb > 0.04045
    rgb[mask] = np.power((rgb[mask] + 0.055) / 1.055, 2.4)
    rgb[~mask] = rgb[~mask] / 12.92
    
    # Convert to XYZ
    # Using D65 illuminant
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041]
    ])
    
    xyz = np.dot(rgb, m.T)
    
    # Normalize by D65 white point
    xyz[:, :, 0] /= 0.95047
    xyz[:, :, 1] /= 1.00000
    xyz[:, :, 2] /= 1.08883
    
    # Convert XYZ to LAB
    mask = xyz > 0.008856
    xyz[mask] = np.power(xyz[mask], 1/3)
    xyz[~mask] = (7.787 * xyz[~mask]) + (16/116)
    
    lab = np.zeros_like(xyz)
    lab[:, :, 0] = (116 * xyz[:, :, 1]) - 16  # L
    lab[:, :, 1] = 500 * (xyz[:, :, 0] - xyz[:, :, 1])  # a
    lab[:, :, 2] = 200 * (xyz[:, :, 1] - xyz[:, :, 2])  # b
    
    return lab


def lab_to_rgb(lab):
    """
    Convert LAB to RGB color space.
    
    Args:
        lab: numpy array in LAB color space
    
    Returns:
        numpy array in range [0, 255] with shape (height, width, 3)
    """
    # Convert LAB to XYZ
    fy = (lab[:, :, 0] + 16) / 116
    fx = lab[:, :, 1] / 500 + fy
    fz = fy - lab[:, :, 2] / 200
    
    xyz = np.stack([fx, fy, fz], axis=2)
    
    mask = xyz > 0.2068966
    xyz[mask] = np.power(xyz[mask], 3)
    xyz[~mask] = (xyz[~mask] - 16/116) / 7.787
    
    # Denormalize by D65 white point
    xyz[:, :, 0] *= 0.95047
    xyz[:, :, 1] *= 1.00000
    xyz[:, :, 2] *= 1.08883
    
    # Convert XYZ to RGB
    m_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252]
    ])
    
    rgb = np.dot(xyz, m_inv.T)
    
    # Apply inverse gamma correction (linear RGB to sRGB)
    mask = rgb > 0.0031308
    rgb[mask] = 1.055 * np.power(rgb[mask], 1/2.4) - 0.055
    rgb[~mask] = 12.92 * rgb[~mask]
    
    # Convert to [0, 255]
    rgb = np.clip(rgb * 255, 0, 255)
    
    return rgb