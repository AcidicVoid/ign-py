import hashlib
from colorspace_conversion import rgb_to_lab, lab_to_rgb
from ign import generate_ign_noise

try:
    from PIL import Image, ImageFilter
    import numpy as np
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install pillow numpy")
    sys.exit(1)

# Common image extensions to process
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif'}

# Windows system default 8bpp palette (256 colors)
# First 10 and last 10 are system reserved colors
WINDOWS_SYSTEM_PALETTE = [
    # First 10 system colors (indices 0-9)
    (0, 0, 0),           # 0: black
    (128, 0, 0),         # 1: dark red
    (0, 128, 0),         # 2: dark green
    (128, 128, 0),       # 3: dark yellow
    (0, 0, 128),         # 4: dark blue
    (128, 0, 128),       # 5: dark magenta
    (0, 128, 128),       # 6: dark cyan
    (192, 192, 192),     # 7: light grey
    (192, 220, 192),     # 8: money green
    (166, 202, 240),     # 9: sky blue
]

# Middle 236 colors (indices 10-245) - standard color cube + grays
# Generate a 6x6x6 color cube (216 colors) + 20 grays
middle_colors = []
# 6x6x6 RGB cube
for r in range(6):
    for g in range(6):
        for b in range(6):
            middle_colors.append((r * 51, g * 51, b * 51))

# Add 20 additional gray shades to fill remaining slots
for i in range(20):
    gray = int(8 + (i * 240 / 19))
    middle_colors.append((gray, gray, gray))

WINDOWS_SYSTEM_PALETTE.extend(middle_colors)

# Last 10 system colors (indices 246-255)
WINDOWS_SYSTEM_PALETTE.extend([
    (255, 251, 240),     # 246: cream
    (160, 160, 164),     # 247: medium grey
    (128, 128, 128),     # 248: dark grey
    (255, 0, 0),         # 249: red
    (0, 255, 0),         # 250: green
    (255, 255, 0),       # 251: yellow
    (0, 0, 255),         # 252: blue
    (255, 0, 255),       # 253: magenta
    (0, 255, 255),       # 254: cyan
    (255, 255, 255),     # 255: white
])

def convert_image(input_path, output_path, noise_scale, strength, blur_radius, palette_mode,
                 normalize, preblur, seed, twopass, colorspace, use_hash=False):
    """
    Convert a single image to 8-bit PNG with interleaved gradient noise dithering.
    
    Args:
        input_path: Path to input image
        output_path: Path to output PNG file (or directory if use_hash=True)
        noise_scale: Scale of the noise pattern (1-8, higher = coarser)
        strength: Noise strength (0.0-1.0, typical: 0.001-0.01)
        blur_radius: Gaussian blur radius for final image (0.0-16.0)
        palette_mode: 'adaptive' or 'system' palette
        normalize: Normalize image color range before dithering
        preblur: Pre-blur radius before dithering (0.0-2.0)
        seed: Noise seed offset (0-1000)
        twopass: Use two-pass quantization
        colorspace: 'rgb' or 'lab' for processing color space
        use_hash: If True, use MD5 hash as filename
    """
    try:
        # Load image
        img = Image.open(input_path)
        
        # Convert to RGB if necessary
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        # Convert RGBA to RGB by compositing on white background
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        
        # Apply pre-blur if specified
        if preblur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=preblur))
        
        # Store original image for palette generation (only needed for system palette)
        original_img = img.copy() if palette_mode == 'system' else None
        
        # Convert to numpy array (float for processing)
        img_array = np.array(img, dtype=np.float32)
        
        # Convert to LAB color space if specified
        if colorspace == 'lab':
            img_array = rgb_to_lab(img_array)
        
        # Normalize img_array range
        if normalize:
            img_array_min = img_array.min()
            img_array_max = img_array.max()
            img_array = (img_array - img_array_min) / (img_array_max - img_array_min) * 255
        
        # Generate IGN noise for dithering with seed
        noise = generate_ign_noise(img.width, img.height, noise_scale, seed)
        
        # Expand noise to match image channels (RGB or LAB)
        noise = np.expand_dims(noise, axis=2)
        noise = np.tile(noise, (1, 1, 3))
        
        # Apply dithering: add noise before quantization
        # Scale noise from [0,1] to [-strength*255, +strength*255]
        noise_scaled = (noise - 0.5) * 2 * strength * 255
        dithered = img_array + noise_scaled
        
        # Clip to valid range
        dithered = np.clip(dithered, 0, 255)
        
        # Convert back to RGB if we were in LAB
        if colorspace == 'lab':
            dithered = lab_to_rgb(dithered)
        
        # Quantize to 8-bit
        quantized = np.floor(dithered).astype(np.uint8)
        
        # Convert back to PIL Image
        result_img = Image.fromarray(quantized, 'RGB')
        
        # Apply palette quantization ONLY for system palette mode
        # Adaptive mode keeps full 8-bit per channel (16.7M colors)
        if palette_mode == 'system':
            # Use Windows system palette
            system_palette_img = Image.new('P', (1, 1))
            # Flatten the palette list for PIL (needs R,G,B,R,G,B,...)
            flat_palette = []
            for r, g, b in WINDOWS_SYSTEM_PALETTE:
                flat_palette.extend([r, g, b])
            system_palette_img.putpalette(flat_palette)
            
            # Convert image to use the system palette
            result_img = result_img.quantize(palette=system_palette_img, dither=Image.NONE)
            # Convert back to RGB mode
            result_img = result_img.convert('RGB')
        
        # Two-pass quantization if enabled
        if twopass:
            # Convert back to numpy for second pass
            img_array_2 = np.array(result_img, dtype=np.float32)
            
            # Generate second noise with different scale and lighter strength
            noise_2 = generate_ign_noise(img.width, img.height, noise_scale * 2, seed + 100)
            noise_2 = np.expand_dims(noise_2, axis=2)
            noise_2 = np.tile(noise_2, (1, 1, 3))
            
            # Apply lighter second pass dithering
            noise_scaled_2 = (noise_2 - 0.5) * 2 * (strength * 0.3) * 255
            dithered_2 = img_array_2 + noise_scaled_2
            dithered_2 = np.clip(dithered_2, 0, 255)
            quantized_2 = np.floor(dithered_2).astype(np.uint8)
            
            result_img = Image.fromarray(quantized_2, 'RGB')
            
            # Re-apply palette quantization only for system mode
            if palette_mode == 'system':
                result_img = result_img.quantize(palette=system_palette_img, dither=Image.NONE)
                result_img = result_img.convert('RGB')
        
        # Apply gaussian blur to final image if radius > 0
        if blur_radius > 0:
            result_img = result_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Determine final output path
        if use_hash:
            # Calculate MD5 hash of the final image
            img_bytes = result_img.tobytes()
            md5_hash = hashlib.md5(img_bytes).hexdigest()
            
            # output_path is actually the directory in this case
            output_dir = Path(output_path)
            final_output = output_dir / f"{md5_hash}.png"
        else:
            final_output = output_path
        
        # Save as PNG
        result_img.save(final_output, 'PNG', optimize=True)
        
        return True, final_output
        
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None