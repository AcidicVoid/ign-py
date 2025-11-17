#!/usr/bin/env python3

import argparse
import sys
import hashlib
from pathlib import Path

try:
    from PIL import Image
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


def generate_ign_noise(width, height, scale=1):
    """
    Generate Interleaved Gradient Noise pattern.
    
    Based on Jorge Jimenez's formula from "Next Generation Post Processing in Call of Duty"
    Formula: frac(52.9829189 * frac(0.06711056 * x + 0.00583715 * y))
    
    Args:
        width: Width of the noise texture
        height: Height of the noise texture
        scale: Scale factor for the noise pattern (default: 1)
    
    Returns:
        numpy array with values in range [0, 1]
    """
    # Create coordinate grids
    x = np.arange(width).reshape(1, -1)
    y = np.arange(height).reshape(-1, 1)
    
    # Apply IGN formula with scale
    x_scaled = x / scale
    y_scaled = y / scale
    
    f = 0.06711056 * x_scaled + 0.00583715 * y_scaled
    noise = np.modf(52.9829189 * np.modf(f)[0])[0]
    
    return noise


def convert_image(input_path, output_path, noise_scale, strength, blur_radius, palette_mode, normalize, use_hash=False):
    """
    Convert a single image to 8-bit PNG with interleaved gradient noise dithering.
    
    Args:
        input_path: Path to input image
        output_path: Path to output PNG file (or directory if use_hash=True)
        noise_scale: Scale of the noise pattern (1-8, higher = coarser)
        strength: Noise strength (0.0-1.0, typical: 0.001-0.01)
        blur_radius: Gaussian blur radius for final image (0.0-16.0)
        palette_mode: 'adaptive' or 'system' palette
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
        
        # Convert to numpy array (float for processing)
        img_array = np.array(img, dtype=np.float32)
        
        # Generate IGN noise for dithering
        noise = generate_ign_noise(img.width, img.height, noise_scale)
        
        # Expand noise to match image channels (RGB)
        noise = np.expand_dims(noise, axis=2)
        noise = np.tile(noise, (1, 1, 3))

        # Normalize img_array range
        if normalize:
            img_array_min = img_array.min()
            img_array_max = img_array.max()
            img_array = (img_array - img_array_min) / (img_array_max - img_array_min) * 255
        
        # Apply dithering: add noise before quantization
        # Scale noise from [0,1] to [-strength*255, +strength*255]
        noise_scaled = (noise - 0.5) * 2 * strength * 255
        dithered = img_array + noise_scaled
        
        # Clip to valid range, for safety
        dithered = np.clip(dithered, 0, 255)

        # Normalize range
        #d_min = dithered.min()
        #d_max = dithered.max()
        #dithered = (dithered - d_min) / (d_max - d_min) * 255
        
        # Quantize to 8-bit (256 colors per channel = 16.7M colors total)
        # This simulates reducing bit depth per channel
        quantized = np.floor(dithered).astype(np.uint8)
        
        # Convert back to PIL Image
        result_img = Image.fromarray(quantized, 'RGB')
        
        # Apply palette quantization based on mode
        if palette_mode == 'system':
            # Use Windows system palette
            palette_img = Image.new('P', (1, 1))
            # Flatten the palette list for PIL (needs R,G,B,R,G,B,...)
            flat_palette = []
            for r, g, b in WINDOWS_SYSTEM_PALETTE:
                flat_palette.extend([r, g, b])
            palette_img.putpalette(flat_palette)
            
            # Convert image to use the system palette
            result_img = result_img.quantize(palette=palette_img, dither=Image.NONE)
        else:
            # Use adaptive palette (median cut)
            result_img = result_img.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE)
        
        # Convert back to RGB mode for PNG saving
        result_img = result_img.convert('RGB')
        
        # Apply gaussian blur to final image if radius > 0
        if blur_radius > 0:
            from PIL import ImageFilter
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
        return False, None


def process_single_image(input_path, output_dir, noise_scale, strength, blur_radius, palette_mode, normalize, use_hash):
    """Process a single image file."""
    input_file = Path(input_path)
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        return False
    
    if not input_file.is_file():
        print(f"Error: Input path is not a file: {input_path}")
        return False
    
    # Determine output path/directory
    if use_hash:
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = input_file.parent
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        if output_dir:
            output_path = Path(output_dir) / f"{input_file.stem}_ignpy.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = input_file.parent / f"{input_file.stem}_ignpy.png"
    
    print(f"Converting: {input_file.name}")
    print(f"Settings: Scale={noise_scale}px, Strength={strength}, Blur={blur_radius}, Palette={palette_mode}, Normalize={normalize}, Hash={use_hash}")
    success, final_path = convert_image(input_file, output_path, noise_scale, strength, blur_radius, palette_mode, use_hash)
    
    if success:
        print(f"✓ Successfully converted to: {final_path}")
        return True
    else:
        return False


def process_directory(input_dir, output_dir, noise_scale, strength, blur_radius, palette_mode, normalize, use_hash):
    """Process all images in a directory."""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return False
    
    if not input_path.is_dir():
        print(f"Error: Input path is not a directory: {input_dir}")
        return False
    
    if not output_dir:
        print("Error: Output directory (-o) is required for batch conversion")
        return False
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all supported images
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(input_path.glob(f"*{ext}"))
        image_files.extend(input_path.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"No supported images found in: {input_dir}")
        print(f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        return False
    
    print(f"Found {len(image_files)} image(s) to convert")
    print(f"Output directory: {output_path}")
    print(f"Settings: Scale={noise_scale}px, Strength={strength}, Blur={blur_radius}, Palette={palette_mode}, Normalize={normalize} Hash={use_hash}\n")
    
    success_count = 0
    fail_count = 0
    
    for img_file in sorted(image_files):
        print(f"Converting: {img_file.name}")
        
        success, final_path = convert_image(img_file, output_path, noise_scale, strength, blur_radius, palette_mode, normalize, use_hash)
        if success:
            success_count += 1
            print(f"✓ Success -> {final_path.name}\n")
        else:
            fail_count += 1
            print(f"✗ Failed\n")
    
    print(f"Conversion complete: {success_count} succeeded, {fail_count} failed")
    return fail_count == 0


def main():
    parser = argparse.ArgumentParser(
        description='Convert images to 8-bit PNG with interleaved gradient noise for debanding',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single image:
    %(prog)s /path/to/image.jpg
    %(prog)s /path/to/image.webp -o /path/to/output/

  Batch conversion:
    %(prog)s -d /path/to/images/ -o /path/to/converted-images/

  Custom noise settings:
    %(prog)s /path/to/image.jpg -n 4 -s 0.005
    %(prog)s -d /path/to/images/ -o /path/to/output/ -n 2 -s 0.008

  With gaussian blur on final image:
    %(prog)s /path/to/image.jpg -b 2.5
    %(prog)s /path/to/image.jpg -n 4 -s 0.008 --blur 3.0

  Using Windows system palette:
    %(prog)s /path/to/image.jpg -p system
    %(prog)s /path/to/image.jpg --palette system -n 2 -s 0.01

  Use MD5 hash as filename:
    %(prog)s /path/to/image.jpg --md5filename
    %(prog)s /path/to/image.jpg -m
    %(prog)s -d /path/to/images/ -o /path/to/output/ --md5filename

Note: Interleaved Gradient Noise (IGN) is used for dithering during color
quantization to 8-bit palette (256 colors). This produces high-quality results
with minimal banding. The -n parameter controls the noise pattern scale,
-s controls the dithering strength, -b applies gaussian blur to the
final image to soften the result, and -p selects between adaptive palette
(optimized per image) or system palette (Windows 256-color standard).
        """
    )
    
    parser.add_argument(
        'input_file',
        nargs='?',
        help='Input image file (for single file conversion)'
    )
    
    parser.add_argument(
        '-d',
        dest='input_dir',
        help='Input directory (for batch conversion)'
    )
    
    parser.add_argument(
        '-o',
        dest='output',
        help='Output directory (required for batch conversion)'
    )
    
    parser.add_argument(
        '-n',
        dest='noise_scale',
        type=int,
        default=1,
        choices=range(1, 9),
        metavar='[1-8]',
        help='Noise scale/coarseness in pixels (default: 1, range: 1-8)'
    )
    
    parser.add_argument(
        '-s',
        dest='strength',
        type=float,
        default=0.005,
        metavar='FLOAT',
        help='Noise strength (default: 0.005, recommended: 0.001-0.01)'
    )
    
    parser.add_argument(
        '-b',
        '--blur',
        dest='blur_radius',
        type=float,
        default=0.0,
        metavar='[0.0-16.0]',
        help='Gaussian blur radius for final image (default: 0.0, range: 0.0-16.0)'
    )
    
    parser.add_argument(
        '-m',
        '--md5filename',
        dest='use_hash',
        action='store_true',
        help='Use MD5 hash of the final image as filename'
    )
    
    parser.add_argument(
        '-p',
        '--palette',
        dest='palette_mode',
        type=str,
        default='adaptive',
        choices=['adaptive', 'system'],
        help='Palette mode: adaptive (default) or system (Windows 256-color palette)'
    )

    parser.add_argument(
        '-r',
        '--range-normalize',
        dest='normalize',
        action='store_true',
        help='Normalizes image color range before dithering. Can help with some 32-Bit images.'
    )
    
    args = parser.parse_args()
    
    # Validate strength
    if args.strength < 0 or args.strength > 1:
        print("Error: Strength must be between 0.0 and 1.0")
        return 1
    
    # Validate blur radius
    if args.blur_radius < 0 or args.blur_radius > 16:
        print("Error: Blur radius must be between 0.0 and 16.0")
        return 1
    
    # Determine mode: single file or batch directory
    if args.input_file and args.input_dir:
        print("Error: Cannot specify both input file and -d directory")
        return 1
    
    if not args.input_file and not args.input_dir:
        print("Error: Must specify either an input file or -d directory")
        parser.print_help()
        return 1
    
    if args.input_file:
        # Single file mode
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input_file}")
            return 1
        success = process_single_image(args.input_file, args.output, args.noise_scale, args.strength, args.blur_radius, args.palette_mode, args.normalize, args.use_hash)
    else:
        # Batch directory mode
        input_path = Path(args.input_dir)
        if not input_path.exists():
            print(f"Error: Input directory not found: {args.input_dir}")
            return 1
        if not input_path.is_dir():
            print(f"Error: Path is not a directory: {args.input_dir}")
            return 1
        success = process_directory(args.input_dir, args.output, args.noise_scale, args.strength, args.blur_radius, args.palette_mode, args.normalize, args.use_hash)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())