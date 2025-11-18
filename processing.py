from pathlib import Path
from image_converter import  convert_image

def process_single_image(input_path, output_dir, noise_scale, strength, blur_radius, palette_mode,
                        normalize, preblur, seed, twopass, colorspace, use_hash):
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
    print(f"Settings: Scale={noise_scale}px, Strength={strength}, Blur={blur_radius}, Palette={palette_mode}")
    print(f"          Normalize={normalize}, PreBlur={preblur}, Seed={seed}, TwoPass={twopass}, ColorSpace={colorspace}, Hash={use_hash}")
    success, final_path = convert_image(input_file, output_path, noise_scale, strength, blur_radius, 
                                       palette_mode, normalize, preblur, seed, twopass, colorspace, use_hash)
    
    if success:
        print(f"✓ Successfully converted to: {final_path}")
        return True
    else:
        return False


def process_directory(input_dir, output_dir, noise_scale, strength, blur_radius, palette_mode, 
                     normalize, preblur, seed, twopass, colorspace, use_hash):
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
    print(f"Settings: Scale={noise_scale}px, Strength={strength}, Blur={blur_radius}, Palette={palette_mode}")
    print(f"          Normalize={normalize}, PreBlur={preblur}, Seed={seed}, TwoPass={twopass}, ColorSpace={colorspace}, Hash={use_hash}\n")
    
    success_count = 0
    fail_count = 0
    
    for img_file in sorted(image_files):
        print(f"Converting: {img_file.name}")
        
        success, final_path = convert_image(img_file, output_path, noise_scale, strength, blur_radius, 
                                           palette_mode, normalize, preblur, seed, twopass, colorspace, use_hash)
        if success:
            success_count += 1
            print(f"✓ Success -> {final_path.name}\n")
        else:
            fail_count += 1
            print(f"✗ Failed\n")
    
    print(f"Conversion complete: {success_count} succeeded, {fail_count} failed")
    return fail_count == 0