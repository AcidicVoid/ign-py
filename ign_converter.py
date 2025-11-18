#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from processing import process_single_image, process_directory

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

  Advanced debanding options:
    %(prog)s /path/to/image.jpg --preblur 0.5 --seed 42 --twopass --colorspace lab
    %(prog)s /path/to/image.jpg -pb 1.0 -sd 100 -tp -cs lab -s 0.008

Note: Interleaved Gradient Noise (IGN) is used for dithering during color
quantization. Advanced options include:
- Adaptive mode: Full 8-bit per channel (16.7M colors) with IGN dithering
- System mode: Windows 256-color palette with IGN dithering
- Pre-blur: Smooths input before dithering to reduce existing artifacts
- Seed: Varies the noise pattern to prevent visible repetition
- Two-pass: Applies a second lighter dithering pass to break up banding
- LAB colorspace: Processes in perceptually uniform color space for better results
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
        help='Palette mode: adaptive (8-bit per channel, 16.7M colors) or system (Windows 256-color palette)'
    )

    parser.add_argument(
        '-r',
        '--range-normalize',
        dest='normalize',
        action='store_true',
        help='Normalizes image color range before dithering. Can help with some 32-Bit images.'
    )
    
    parser.add_argument(
        '-pb',
        '--preblur',
        dest='preblur',
        type=float,
        default=0.0,
        metavar='[0.0-2.0]',
        help='Pre-blur radius before dithering (default: 0.0, range: 0.0-2.0). Smooths existing artifacts.'
    )
    
    parser.add_argument(
        '-sd',
        '--seed',
        dest='seed',
        type=int,
        default=0,
        metavar='[0-1000]',
        help='Noise seed offset (default: 0, range: 0-1000). Varies the noise pattern.'
    )
    
    parser.add_argument(
        '-tp',
        '--twopass',
        dest='twopass',
        action='store_true',
        help='Use two-pass quantization. Applies a second lighter dithering pass to reduce banding.'
    )
    
    parser.add_argument(
        '-cs',
        '--colorspace',
        dest='colorspace',
        type=str,
        default='rgb',
        choices=['rgb', 'lab'],
        help='Color space for processing: rgb (default) or lab (perceptually uniform)'
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
    
    # Validate preblur
    if args.preblur < 0 or args.preblur > 2:
        print("Error: Pre-blur must be between 0.0 and 2.0")
        return 1
    
    # Validate seed
    if args.seed < -1 or args.seed > 1000:
        print("Error: Seed must be between 0 and 1000")
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
        success = process_single_image(args.input_file, args.output, args.noise_scale, args.strength, 
                                      args.blur_radius, args.palette_mode, args.normalize, args.preblur, 
                                      args.seed, args.twopass, args.colorspace, args.use_hash)
    else:
        # Batch directory mode
        input_path = Path(args.input_dir)
        if not input_path.exists():
            print(f"Error: Input directory not found: {args.input_dir}")
            return 1
        if not input_path.is_dir():
            print(f"Error: Path is not a directory: {args.input_dir}")
            return 1
        success = process_directory(args.input_dir, args.output, args.noise_scale, args.strength, 
                                   args.blur_radius, args.palette_mode, args.normalize, args.preblur, 
                                   args.seed, args.twopass, args.colorspace, args.use_hash)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())