from construct import *
import struct
import io
import math
import bpy

TextureFormats = Enum(Int8ub,
    I4 = 0x03,
    I8 = 0x04,
    IA4 = 0x05,
    IA8 = 0x06,
    RGB565 = 0x07,
    RGB5A3 = 0x08,
    RGBA32 = 0x09,
    CMPR = 0x0a
)

def calc_img_size(fmt, w, h):
    # Custom MK Wiki has decent documentation on the texture formats, so check there if you're interested!
    # Just so you know, the first zeroes are there because I need to pad out the list
    bpp = [4, 8, 8, 16, 16, 16, 32, 0, 4, 8, 16, 0, 0, 0, 4]
    tile_size_w = [8, 8, 8, 4, 4, 4, 4, 0, 8, 8, 4, 0, 0, 0, 8]
    tile_size_h = [8, 4, 4, 4, 4, 4, 4, 0, 8, 4, 4, 0, 0, 0, 8]
    while w % tile_size_w[int(fmt)] != 0:
        w += 1
    while h % tile_size_h[int(fmt)] != 0:
        h += 1
    return (w * h * bpp[int(fmt)]) // 8


# Format enum (you can map these to your texture.format values)
class TextureFormat:
    I4 = 0x03      # 4-bit intensity
    I8 = 0x04      # 8-bit intensity
    IA4 = 0x05     # 4-bit intensity + 4-bit alpha
    IA8 = 0x06     # 8-bit intensity + 8-bit alpha
    RGB565 = 0x07  # 16-bit RGB (no alpha)
    RGB5A3 = 0x08  # 16-bit RGB with 3-bit alpha OR 15-bit RGB
    RGBA32 = 0x09  # 32-bit RGBA (stored as separate AR and GB blocks)
    CMPR = 0x0A    # Compressed (DXT1/S3TC)


def decode_i4(data, width, height):
    """
    Decode I4 (4-bit intensity) texture
    2 pixels per byte, stored in 8x8 tiles
    """
    pixels = []
    
    # I4 uses 8x8 tiles
    tile_width = (width + 7) // 8
    tile_height = (height + 7) // 8
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 8x8 tile
            for y in range(8):
                for x in range(0, 8, 2):  # 2 pixels per byte
                    if src_offset >= len(data):
                        break
                    
                    byte = data[src_offset]
                    src_offset += 1
                    
                    # First pixel (high nibble)
                    intensity1 = (byte >> 4) & 0x0F
                    intensity1 = (intensity1 * 255) // 15  # Expand 4-bit to 8-bit
                    
                    # Second pixel (low nibble)
                    intensity2 = byte & 0x0F
                    intensity2 = (intensity2 * 255) // 15
                    
                    # Calculate actual pixel positions
                    px1 = tx * 8 + x
                    py1 = ty * 8 + y
                    px2 = tx * 8 + x + 1
                    py2 = ty * 8 + y
                    
                    # Store pixels (RGBA format for Blender)
                    if px1 < width and py1 < height:
                        pixel_idx = (py1 * width + px1) * 4
                        if pixel_idx + 3 < len(pixels):
                            pixels[pixel_idx:pixel_idx+4] = [intensity1/255.0, intensity1/255.0, intensity1/255.0, 1.0]
                    
                    if px2 < width and py2 < height:
                        pixel_idx = (py2 * width + px2) * 4
                        if pixel_idx + 3 < len(pixels):
                            pixels[pixel_idx:pixel_idx+4] = [intensity2/255.0, intensity2/255.0, intensity2/255.0, 1.0]
    
    # Pre-allocate array
    pixels = [0.0] * (width * height * 4)
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            for y in range(8):
                for x in range(0, 8, 2):
                    if src_offset >= len(data):
                        byte = 0
                    else:
                        byte = data[src_offset]
                    src_offset += 1
                    
                    intensity1 = ((byte >> 4) & 0x0F) * 17  # 0-15 -> 0-255 (17 = 255/15)
                    intensity2 = (byte & 0x0F) * 17
                    
                    px1 = tx * 8 + x
                    py1 = ty * 8 + y
                    
                    if px1 < width and py1 < height:
                        idx = (py1 * width + px1) * 4
                        pixels[idx] = intensity1 / 255.0
                        pixels[idx+1] = intensity1 / 255.0
                        pixels[idx+2] = intensity1 / 255.0
                        pixels[idx+3] = 1.0
                    
                    if px1 + 1 < width and py1 < height:
                        idx = (py1 * width + px1 + 1) * 4
                        pixels[idx] = intensity2 / 255.0
                        pixels[idx+1] = intensity2 / 255.0
                        pixels[idx+2] = intensity2 / 255.0
                        pixels[idx+3] = 1.0
    
    return pixels


def decode_i8(data, width, height):
    """
    Decode I8 (8-bit intensity) texture
    1 byte per pixel, stored in 8x4 tiles
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 7) // 8
    tile_height = (height + 3) // 4
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 8x4 tile
            for y in range(4):
                for x in range(8):
                    if src_offset >= len(data):
                        intensity = 0
                    else:
                        intensity = data[src_offset]
                    src_offset += 1
                    
                    px = tx * 8 + x
                    py = ty * 4 + y
                    
                    if px < width and py < height:
                        idx = (py * width + px) * 4
                        pixels[idx] = intensity / 255.0
                        pixels[idx+1] = intensity / 255.0
                        pixels[idx+2] = intensity / 255.0
                        pixels[idx+3] = 1.0
    
    return pixels


def decode_ia4(data, width, height):
    """
    Decode IA4 (4-bit intensity + 4-bit alpha) texture
    1 byte per pixel (4-bit I, 4-bit A), stored in 8x4 tiles
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 7) // 8
    tile_height = (height + 3) // 4
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 8x4 tile
            for y in range(4):
                for x in range(8):
                    if src_offset >= len(data):
                        byte = 0
                    else:
                        byte = data[src_offset]
                    src_offset += 1
                    
                    alpha = (byte >> 4) & 0x0F
                    intensity = byte & 0x0F
                    
                    # Expand 4-bit to 8-bit
                    alpha = alpha * 17
                    intensity = intensity * 17
                    
                    px = tx * 8 + x
                    py = ty * 4 + y
                    
                    if px < width and py < height:
                        idx = (py * width + px) * 4
                        pixels[idx] = intensity / 255.0
                        pixels[idx+1] = intensity / 255.0
                        pixels[idx+2] = intensity / 255.0
                        pixels[idx+3] = alpha / 255.0
    
    return pixels


def decode_ia8(data, width, height):
    """
    Decode IA8 (8-bit intensity + 8-bit alpha) texture
    2 bytes per pixel, stored in 4x4 tiles
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 3) // 4
    tile_height = (height + 3) // 4
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 4x4 tile
            for y in range(4):
                for x in range(4):
                    if src_offset + 1 >= len(data):
                        alpha = 255
                        intensity = 0
                    else:
                        alpha = data[src_offset]
                        intensity = data[src_offset + 1]
                    src_offset += 2
                    
                    px = tx * 4 + x
                    py = ty * 4 + y
                    
                    if px < width and py < height:
                        idx = (py * width + px) * 4
                        pixels[idx] = intensity / 255.0
                        pixels[idx+1] = intensity / 255.0
                        pixels[idx+2] = intensity / 255.0
                        pixels[idx+3] = alpha / 255.0
    
    return pixels


def decode_rgb565(data, width, height):
    """
    Decode RGB565 texture
    2 bytes per pixel (5-bit R, 6-bit G, 5-bit B), stored in 4x4 tiles
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 3) // 4
    tile_height = (height + 3) // 4
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 4x4 tile
            for y in range(4):
                for x in range(4):
                    if src_offset + 1 >= len(data):
                        rgb565 = 0
                    else:
                        rgb565 = struct.unpack('>H', data[src_offset:src_offset+2])[0]
                    src_offset += 2
                    
                    # Extract RGB components
                    r = (rgb565 >> 11) & 0x1F
                    g = (rgb565 >> 5) & 0x3F
                    b = rgb565 & 0x1F
                    
                    # Expand to 8-bit (scale to 0-255)
                    r = (r * 255) // 31
                    g = (g * 255) // 63
                    b = (b * 255) // 31
                    
                    px = tx * 4 + x
                    py = ty * 4 + y
                    
                    if px < width and py < height:
                        idx = (py * width + px) * 4
                        pixels[idx] = r / 255.0
                        pixels[idx+1] = g / 255.0
                        pixels[idx+2] = b / 255.0
                        pixels[idx+3] = 1.0
    
    return pixels


def decode_rgb5a3(data, width, height):
    """
    Decode RGB5A3 texture
    2 bytes per pixel, format depends on high bit:
    - If bit 15 = 1: RGB555 (no alpha)
    - If bit 15 = 0: RGB444 + A3 (3-bit alpha)
    Stored in 4x4 tiles
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 3) // 4
    tile_height = (height + 3) // 4
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Process 4x4 tile
            for y in range(4):
                for x in range(4):
                    if src_offset + 1 >= len(data):
                        rgb5a3 = 0
                    else:
                        rgb5a3 = struct.unpack('>H', data[src_offset:src_offset+2])[0]
                    src_offset += 2
                    
                    if rgb5a3 & 0x8000:
                        # RGB555 format (no alpha)
                        r = (rgb5a3 >> 10) & 0x1F
                        g = (rgb5a3 >> 5) & 0x1F
                        b = rgb5a3 & 0x1F
                        a = 255
                        
                        # Expand 5-bit to 8-bit
                        r = (r * 255) // 31
                        g = (g * 255) // 31
                        b = (b * 255) // 31
                    else:
                        # RGB444 + A3 format
                        a = (rgb5a3 >> 12) & 0x07
                        r = (rgb5a3 >> 8) & 0x0F
                        g = (rgb5a3 >> 4) & 0x0F
                        b = rgb5a3 & 0x0F
                        
                        # Expand to 8-bit
                        a = (a * 255) // 7
                        r = (r * 255) // 15
                        g = (g * 255) // 15
                        b = (b * 255) // 15
                    
                    px = tx * 4 + x
                    py = ty * 4 + y
                    
                    if px < width and py < height:
                        idx = (py * width + px) * 4
                        pixels[idx] = r / 255.0
                        pixels[idx+1] = g / 255.0
                        pixels[idx+2] = b / 255.0
                        pixels[idx+3] = a / 255.0
    
    return pixels

#FIXME: Bugged! This won't always work, but at least it returns black pixels rather than failing the add-on.
def decode_rgba32(data, width, height):
    """
    Decode RGBA32 (RGBA8) texture from GameCube/Wii format
    
    RGBA32 is stored in 4x4 tiles with AR and GB blocks:
    - First 32 bytes: AR AR AR AR... (16 pixels, 2 bytes each)
    - Next 32 bytes: GB GB GB GB... (16 pixels, 2 bytes each)
    """
    import io
    
    stream = io.BytesIO(data)
    num_blocks_w = (width + 3) // 4  # Round up
    num_blocks_h = (height + 3) // 4
    
    # Allocate pixel array (RGBA, 4 bytes per pixel)
    pixels = bytearray(width * height * 4)
    
    for y_block in range(num_blocks_h):
        for x_block in range(num_blocks_w):
            # Each 4x4 block has 64 bytes total:
            # - 32 bytes AR (Alpha + Red)
            # - 32 bytes GB (Green + Blue)
            
            # Read AR block (32 bytes)
            ar_data = stream.read(32)
            
            # Read GB block (32 bytes)
            gb_data = stream.read(32)
            
            # Process each pixel in the 4x4 tile
            for py in range(4):
                for px in range(4):
                    # Calculate actual pixel position
                    pixel_x = x_block * 4 + px
                    pixel_y = y_block * 4 + py
                    
                    # Skip if outside image bounds
                    if pixel_x >= width or pixel_y >= height:
                        continue
                    
                    # Calculate destination index in output array
                    dest_index = (pixel_y * width + pixel_x) * 4
                    
                    # Calculate source index within the 4x4 tile
                    tile_index = py * 4 + px
                    ar_offset = tile_index * 2
                    gb_offset = tile_index * 2
                    
                    # Extract ARGB values
                    a = ar_data[ar_offset] if ar_offset < len(ar_data) else 255
                    r = ar_data[ar_offset + 1] if ar_offset + 1 < len(ar_data) else 0
                    g = gb_data[gb_offset] if gb_offset < len(gb_data) else 0
                    b = gb_data[gb_offset + 1] if gb_offset + 1 < len(gb_data) else 0
                    
                    # Store as RGBA
                    pixels[dest_index + 0] = r
                    pixels[dest_index + 1] = g
                    pixels[dest_index + 2] = b
                    pixels[dest_index + 3] = a
    
    return list(pixels)


def decode_cmpr(data, width, height):
    """
    Decode CMPR (DXT1/S3TC compressed) texture
    Each 8x8 tile contains four 4x4 DXT1 blocks
    Each DXT1 block is 8 bytes:
    - 2 bytes: color0 (RGB565)
    - 2 bytes: color1 (RGB565)
    - 4 bytes: 2-bit indices for 16 pixels
    """
    pixels = [0.0] * (width * height * 4)
    
    tile_width = (width + 7) // 8
    tile_height = (height + 7) // 8
    
    src_offset = 0
    
    for ty in range(tile_height):
        for tx in range(tile_width):
            # Each 8x8 tile has 4 DXT1 blocks in this order:
            # [0][1]
            # [2][3]
            sub_blocks = [(0, 0), (4, 0), (0, 4), (4, 4)]
            
            for sub_x, sub_y in sub_blocks:
                if src_offset + 8 > len(data):
                    src_offset += 8
                    continue
                
                # Read DXT1 block
                color0 = struct.unpack('>H', data[src_offset:src_offset+2])[0]
                color1 = struct.unpack('>H', data[src_offset+2:src_offset+4])[0]
                indices = struct.unpack('>I', data[src_offset+4:src_offset+8])[0]
                src_offset += 8
                
                # Decode color0 and color1 from RGB565
                r0 = ((color0 >> 11) & 0x1F) * 255 // 31
                g0 = ((color0 >> 5) & 0x3F) * 255 // 63
                b0 = (color0 & 0x1F) * 255 // 31
                
                r1 = ((color1 >> 11) & 0x1F) * 255 // 31
                g1 = ((color1 >> 5) & 0x3F) * 255 // 63
                b1 = (color1 & 0x1F) * 255 // 31
                
                # Generate color palette
                colors = []
                colors.append((r0, g0, b0, 255))
                colors.append((r1, g1, b1, 255))
                
                if color0 > color1:
                    # 4-color mode
                    colors.append((
                        (2 * r0 + r1) // 3,
                        (2 * g0 + g1) // 3,
                        (2 * b0 + b1) // 3,
                        255
                    ))
                    colors.append((
                        (r0 + 2 * r1) // 3,
                        (g0 + 2 * g1) // 3,
                        (b0 + 2 * b1) // 3,
                        255
                    ))
                else:
                    # 3-color mode with transparent
                    colors.append((
                        (r0 + r1) // 2,
                        (g0 + g1) // 2,
                        (b0 + b1) // 2,
                        255
                    ))
                    colors.append((0, 0, 0, 0))  # Transparent
                
                # Decode 4x4 block
                for y in range(4):
                    for x in range(4):
                        pixel_idx = y * 4 + x
                        color_idx = (indices >> (30 - pixel_idx * 2)) & 0x03
                        
                        r, g, b, a = colors[color_idx]
                        
                        px = tx * 8 + sub_x + x
                        py = ty * 8 + sub_y + y
                        
                        if px < width and py < height:
                            idx = (py * width + px) * 4
                            pixels[idx] = r / 255.0
                            pixels[idx+1] = g / 255.0
                            pixels[idx+2] = b / 255.0
                            pixels[idx+3] = a / 255.0
    
    return pixels
'''
def encode_cmpr(rgba_data, width, height):
    """
    Encode RGBA data to CMPR (DXT1) format for GameCube/Wii
    
    Args:
        rgba_data: bytes or bytearray with RGBA pixels (4 bytes per pixel)
        width: texture width (must be multiple of 8)
        height: texture height (must be multiple of 8)
    
    Returns:
        bytes: Encoded CMPR data
    """
    import struct
    
    # Validate input
    if not isinstance(rgba_data, (bytes, bytearray)):
        raise TypeError(f"rgba_data must be bytes or bytearray, got {type(rgba_data).__name__}")
    
    if width % 8 != 0 or height % 8 != 0:
        raise ValueError(f"Width and height must be multiples of 8, got {width}x{height}")
    
    expected_size = width * height * 4
    if len(rgba_data) != expected_size:
        raise ValueError(
            f"Invalid data size. Expected {expected_size} bytes for {width}x{height} RGBA, "
            f"got {len(rgba_data)} bytes"
        )
    
    # CMPR uses 8x8 tiles, each containing four 4x4 DXT1 blocks
    num_tiles_w = width // 8
    num_tiles_h = height // 8
    
    encoded_data = bytearray()
    
    for tile_y in range(num_tiles_h):
        for tile_x in range(num_tiles_w):
            # Each 8x8 tile contains four 4x4 DXT1 blocks in this order:
            # [0] [1]
            # [2] [3]
            
            for sub_y in range(2):
                for sub_x in range(2):
                    # Get 4x4 block position
                    block_x = tile_x * 8 + sub_x * 4
                    block_y = tile_y * 8 + sub_y * 4
                    
                    # Extract 4x4 block of pixels
                    block_pixels = []
                    for py in range(4):
                        for px in range(4):
                            pixel_x = block_x + px
                            pixel_y = block_y + py
                            
                            if pixel_x >= width or pixel_y >= height:
                                # Padding pixel
                                block_pixels.append((0, 0, 0, 255))
                            else:
                                idx = (pixel_y * width + pixel_x) * 4
                                r = rgba_data[idx + 0]
                                g = rgba_data[idx + 1]
                                b = rgba_data[idx + 2]
                                a = rgba_data[idx + 3]
                                block_pixels.append((r, g, b, a))
                    
                    # Encode this 4x4 block as DXT1
                    dxt1_block = encode_dxt1_block(block_pixels)
                    encoded_data.extend(dxt1_block)
    
    return bytes(encoded_data)


def encode_dxt1_block(pixels):
    """
    Encode a 4x4 block of RGBA pixels to DXT1 format (8 bytes)
    
    Args:
        pixels: List of 16 tuples (r, g, b, a), each 0-255
    
    Returns:
        bytes: 8-byte DXT1 block
    """
    import struct
    
    # Find min and max colors (ignoring fully transparent pixels for DXT1)
    colors = []
    has_alpha = False
    
    for r, g, b, a in pixels:
        if a < 128:  # Treat as transparent
            has_alpha = True
        else:
            colors.append((r, g, b))
    
    if not colors:
        # All transparent - encode as black transparent block
        return struct.pack('>HH', 0, 0) + b'\xFF\xFF\xFF\xFF'
    
    # Find the two most distant colors (simple approach)
    color0, color1 = find_extreme_colors(colors)
    
    # Convert to RGB565
    c0_565 = rgb888_to_rgb565(color0)
    c1_565 = rgb888_to_rgb565(color1)
    
    # DXT1 requires color0 > color1 for opaque, color0 <= color1 for 1-bit alpha
    if has_alpha:
        if c0_565 > c1_565:
            c0_565, c1_565 = c1_565, c0_565
            color0, color1 = color1, color0
    else:
        if c0_565 < c1_565:
            c0_565, c1_565 = c1_565, c0_565
            color0, color1 = color1, color0
    
    # Generate color palette
    if has_alpha:
        # 1-bit alpha mode: c0, c1, (c0+c1)/2, transparent
        palette = [
            color0,
            color1,
            ((color0[0] + color1[0]) // 2,
             (color0[1] + color1[1]) // 2,
             (color0[2] + color1[2]) // 2),
            (0, 0, 0)  # Transparent (index 3)
        ]
    else:
        # Opaque mode: c0, c1, (2*c0+c1)/3, (c0+2*c1)/3
        palette = [
            color0,
            color1,
            ((2 * color0[0] + color1[0]) // 3,
             (2 * color0[1] + color1[1]) // 3,
             (2 * color0[2] + color1[2]) // 3),
            ((color0[0] + 2 * color1[0]) // 3,
             (color0[1] + 2 * color1[1]) // 3,
             (color0[2] + 2 * color1[2]) // 3)
        ]
    
    # Encode indices (2 bits per pixel, 16 pixels = 4 bytes)
    indices = 0
    
    for i, (r, g, b, a) in enumerate(pixels):
        if has_alpha and a < 128:
            # Transparent
            index = 3
        else:
            # Find closest palette color
            index = find_closest_color((r, g, b), palette)
        
        # Pack 2-bit index (MSB first for GameCube)
        indices |= (index << ((15 - i) * 2))
    
    # Pack as big-endian: color0 (2 bytes) + color1 (2 bytes) + indices (4 bytes)
    block = struct.pack('>HH', c0_565, c1_565)
    block += struct.pack('>I', indices)
    
    return block


def find_extreme_colors(colors):
    """
    Find two most distant colors in the list (simple bounding box method)
    
    Args:
        colors: List of (r, g, b) tuples
    
    Returns:
        tuple: (color0, color1) - the two extreme colors
    """
    if len(colors) == 1:
        return colors[0], colors[0]
    
    # Find bounding box
    min_r = min(c[0] for c in colors)
    max_r = max(c[0] for c in colors)
    min_g = min(c[1] for c in colors)
    max_g = max(c[1] for c in colors)
    min_b = min(c[2] for c in colors)
    max_b = max(c[2] for c in colors)
    
    # Find which axis has the greatest range
    r_range = max_r - min_r
    g_range = max_g - min_g
    b_range = max_b - min_b
    
    if r_range >= g_range and r_range >= b_range:
        # Red has greatest range
        color0 = min(colors, key=lambda c: c[0])
        color1 = max(colors, key=lambda c: c[0])
    elif g_range >= b_range:
        # Green has greatest range
        color0 = min(colors, key=lambda c: c[1])
        color1 = max(colors, key=lambda c: c[1])
    else:
        # Blue has greatest range
        color0 = min(colors, key=lambda c: c[2])
        color1 = max(colors, key=lambda c: c[2])
    
    return color0, color1


def rgb888_to_rgb565(color):
    """
    Convert RGB888 to RGB565 format
    
    Args:
        color: Tuple (r, g, b) with values 0-255
    
    Returns:
        int: RGB565 value (16-bit)
    """
    r, g, b = color
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    
    return (r5 << 11) | (g6 << 5) | b5


def find_closest_color(color, palette):
    """
    Find the closest color in the palette using Euclidean distance
    
    Args:
        color: Tuple (r, g, b)
        palette: List of (r, g, b) tuples
    
    Returns:
        int: Index of closest color in palette
    """
    min_dist = float('inf')
    closest_idx = 0
    
    r, g, b = color
    
    for i, (pr, pg, pb) in enumerate(palette):
        # Euclidean distance in RGB space
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
    
    return closest_idx


def calculate_cmpr_size(width, height):
    """
    Calculate the size of CMPR encoded data
    
    Args:
        width: Texture width
        height: Texture height
    
    Returns:
        int: Size in bytes
    """
    # CMPR uses 8x8 tiles, each tile has four 4x4 DXT1 blocks
    # Each DXT1 block is 8 bytes
    num_tiles_w = (width + 7) // 8
    num_tiles_h = (height + 7) // 8
    
    return num_tiles_w * num_tiles_h * 4 * 8
'''

def decode_texture(texture_data, width, height, format_type):
    """
    Main texture decoding function
    
    Args:
        texture_data: Raw texture bytes
        width: Texture width in pixels
        height: Texture height in pixels
        format_type: One of the TextureFormat enum values
    
    Returns:
        List of floats in RGBA format (0.0-1.0) suitable for Blender
        Length = width * height * 4
    """
    decoders = {
        TextureFormat.I4: decode_i4,
        TextureFormat.I8: decode_i8,
        TextureFormat.IA4: decode_ia4,
        TextureFormat.IA8: decode_ia8,
        TextureFormat.RGB565: decode_rgb565,
        TextureFormat.RGB5A3: decode_rgb5a3,
        TextureFormat.RGBA32: decode_rgba32,
        TextureFormat.CMPR: decode_cmpr,
    }
    
    decoder = decoders.get(format_type)
    if decoder is None:
        raise ValueError(f"Unsupported texture format: {format_type}")
    
    return decoder(texture_data, width, height)


def calculate_texture_size(width, height, format_type):
    """
    Calculate the size in bytes of texture data
    
    Args:
        width: Texture width
        height: Texture height
        format_type: TextureFormat enum value
    
    Returns:
        Size in bytes
    """
    sizes = {
        TextureFormat.I4: (width * height) // 2,
        TextureFormat.I8: width * height,
        TextureFormat.IA4: width * height,
        TextureFormat.IA8: width * height * 2,
        TextureFormat.RGB565: width * height * 2,
        TextureFormat.RGB5A3: width * height * 2,
        TextureFormat.RGBA32: width * height * 4,
        TextureFormat.CMPR: ((width + 3) // 4) * ((height + 3) // 4) * 8,
    }
    
    return sizes.get(format_type, 0)

def invert4(m):
    n = 4
    A = [row[:] + [1 if i==j else 0 for j in range(n)] for i,row in enumerate(m)]

    for i in range(n):
        f = A[i][i]
        for j in range(2*n):
            A[i][j] /= f
        for k in range(n):
            if k != i:
                f = A[k][i]
                for j in range(2*n):
                    A[k][j] -= f * A[i][j]

    return [row[n:] for row in A]

def invert4(m):
    n = 4
    A = [row[:] + [1 if i==j else 0 for j in range(n)] for i,row in enumerate(m)]

    for i in range(n):
        f = A[i][i]
        for j in range(2*n):
            A[i][j] /= f
        for k in range(n):
            if k != i:
                f = A[k][i]
                for j in range(2*n):
                    A[k][j] -= f * A[i][j]

    return [row[n:] for row in A]

def transpose(m):
    rows = len(m)
    cols = len(m[0])

    t = [[0]*rows for _ in range(cols)]

    for i in range(rows):
        for j in range(cols):
            t[j][i] = m[i][j]

    return t

def decompose_matrix(m):

    t = [m[0][3], m[1][3], m[2][3]]

    sx = math.sqrt(m[0][0]**2 + m[1][0]**2 + m[2][0]**2)
    sy = math.sqrt(m[0][1]**2 + m[1][1]**2 + m[2][1]**2)
    sz = math.sqrt(m[0][2]**2 + m[1][2]**2 + m[2][2]**2)

    s = [sx, sy, sz]

    r = [
        [m[0][0]/sx, m[0][1]/sy, m[0][2]/sz],
        [m[1][0]/sx, m[1][1]/sy, m[1][2]/sz],
        [m[2][0]/sx, m[2][1]/sy, m[2][2]/sz]
    ]

    return t, r, s

def traverse_node_graph(mdl, arm, index, parent_index=-1):

    node = mdl.nodes[index]
    if parent_index >= 0:
        try:
            try:
                arm.edit_bones[f"Bone_{index}"].parent = arm.edit_bones[f"Bone_{parent_index}"]
            except KeyError:
                arm.edit_bones[f"Bone_{index}"].parent = arm.edit_bones[f"Mesh_{parent_index}"]
        except KeyError:
            try:
                arm.edit_bones[f"Mesh_{index}"].parent = arm.edit_bones[f"Mesh_{parent_index}"]
            except KeyError:
                arm.edit_bones[f"Mesh_{index}"].parent = arm.edit_bones[f"Bone_{parent_index}"]

    if node.child_index_shift > 0:
        traverse_node_graph(mdl, arm, index + node.child_index_shift, index)

    if node.sibling_index_shift > 0:
        traverse_node_graph(mdl, arm, index + node.sibling_index_shift, parent_index)

##############################
Color8 = Struct("r" / Int8ub, "g" / Int8ub, "b" / Int8ub, "a" / Int8ub)  
Vector2 = Struct("x" / Float32b, "y" / Float32b)  
Vector3 = Struct("x" / Float32b, "y" / Float32b, "z" / Float32b)  
  
MDLHeader = Struct(  
    "magic" / Const(0x04B40000, Int32ub),  
    "face_count" / Int16ub,  
    "padding" / Padding(2),  
    "node_count" / Int16ub,  
    "packet_count" / Int16ub,  
    "weight_count" / Int16ub,  
    "joint_count" / Int16ub,  
    "vertex_count" / Int16ub,  
    "normal_count" / Int16ub,  
    "color_count" / Int16ub,  
    "texcoord_count" / Int16ub,  
    "padding2" / Padding(8),  
    "texture_count" / Int16ub,  
    "padding3" / Int16ub,  
    "sampler_count" / Int16ub,  
    "draw_element_count" / Int16ub,  
    "material_count" / Int16ub,  
    "shape_count" / Int16ub,  
    "padding4" / Padding(4),  
    "node_offset" / Int32ub,  
    "packet_offset" / Int32ub,  
    "matrix_offset" / Int32ub,  
    "weight_offset" / Int32ub,  
    "joint_index_offset" / Int32ub,  
    "weight_count_table_offset" / Int32ub,  
    "vertex_offset" / Int32ub,  
    "normal_offset" / Int32ub,  
    "color_offset" / Int32ub,  
    "texcoord_offset" / Int32ub,  
    "padding5" / Padding(8),  
    "texture_offset_array_offset" / Int32ub,  
    "padding6" / Padding(4),  
    "material_offset" / Int32ub,  
    "sampler_offset" / Int32ub,  
    "shape_offset" / Int32ub,  
    "draw_element_offset" / Int32ub,  
    "padding7" / Padding(8)  
)  
  
SceneGraphNode = Struct(  
    "inverse_matrix_index" / Int16ub,  
    "child_index_shift" / Int16ub,  
    "sibling_index_shift" / Int16ub,  
    "padding" / Padding(2),  
    "draw_element_count" / Int16ub,  
    "draw_element_begin_index" / Int16ub,  
    "padding2" / Padding(4)  
)  
  
DrawElement = Struct(  
    "material_index" / Int16ub,  
    "shape_index" / Int16ub  
)  
  
Shape = Struct(  
    "normal_flags" / Int8ub,  
    "unknown1" / Int8ub,  
    "surface_flags" / Int8ub,  
    "unknown2" / Int8ub,  
    "packet_count" / Int16ub,  
    "packet_begin_index" / Int16ub  
)  

VertexData = Struct(
    "matrix_index" / Int8sb,
    "matrix_data_index" / If(
        lambda ctx: ctx.matrix_index != -1,
        Computed(
            lambda ctx: ctx._._.matrix_indices_final[ctx.matrix_index // 3]
            if 0 <= (ctx.matrix_index // 3) < len(ctx._._.matrix_indices_final)
            else 0
        )
    ),
    "tex0_matrix_index" / Int8sb,
    "tex1_matrix_index" / Int8sb,
    "position_index" / Int16ub,
    "normal_index" / If(lambda ctx: ctx._._._.header.normal_count > 0, Int16ub),
    "color_index" / If(lambda ctx: ctx._._._.header.color_count > 0, Int16ub),
    "texcoord_index" / If(lambda ctx: ctx._._._.header.texcoord_count > 0, Int16ub)
)
  
VertexDataShadow = Struct(  
    "matrix_index" / Int8sb,  
    "position_index" / Int16ub,  
    "normal_index" / If(lambda ctx: ctx._._._.header.normal_count > 0, Int8ub)  
)  

Opcode = Enum(Int8ub,
    GX_TRIANGLE=0x90,
    GX_TRIANGLESTRIP=0x98,
    GX_TRIANGLEFAN=0xA0
)

PacketData = Struct(  
    "opcode" / Opcode,  
    "vertex_count" / Int16ub,  
    "vertices" / If(lambda ctx: ctx.opcode != 0, VertexData[lambda ctx: int(ctx.vertex_count)])  
)  
  
Packet = Struct(  
    "data_offset" / Int32ub,  
    "data_size" / Int32ub,  
    "unknown" / Int16ub,  
    "matrix_count" / Int16ub,  
    "matrix_indices" / Int16ub[10],
    "matrix_indices_final" / Computed(lambda ctx: [m for m in ctx.matrix_indices[:ctx.matrix_count] if m != 65535]),
    "data" / Pointer(this.data_offset, PacketData)
)  
  
TevStage = Struct(  
    "unknown" / Int16ub,  
    "sampler_index" / Int16ub,  
    "unknown_floats" / Float32b[7]  
)  
  
Material = Struct(  
    "diffuse_color" / Color8,  
    "unknown" / Int16ub,  
    "alpha_flags" / Int8ub,  
    "tev_stage_count" / Int8ub,  
    "unknown2" / Int8ub,  
    "padding" / Padding(23),  
    "tev_stages" / TevStage[this.tev_stage_count]  
)  

WrapMode = Enum(Int8ub, 
    REPEAT=0x0,
    EXTEND=0x01,
    MIRROR=0x02
)

Sampler = Struct(  
    "texture_index" / Int16ub,  
    "unknown_index" / Int16ub,  
    "wrap_mode_u" / WrapMode,  
    "wrap_mode_v" / WrapMode,  
    "min_filter" / Int8ub,  
    "mag_filter" / Int8ub  
)  
  
Texture = Struct(  
    "format" / TextureFormats,  
    "padding" / Padding(1),  
    "width" / Int16ub,  
    "height" / Int16ub,  
    "padding2" / Padding(26),
    "texdata" / Bytes(lambda ctx: calc_img_size(ctx.format, ctx.width, ctx.height))  
)  

MDL = Struct(  
    "header" / MDLHeader,  
      
    "nodes" / Pointer(this.header.node_offset, SceneGraphNode[lambda ctx: ctx.header.node_count]),  
    "packets" / Pointer(this.header.packet_offset, Packet[lambda ctx: ctx.header.packet_count * 2]),  # *2 for shadow meshes  
    "draw_elements" / Pointer(this.header.draw_element_offset, DrawElement[lambda ctx: ctx.header.draw_element_count]),  
    "materials" / Pointer(this.header.material_offset, Material[lambda ctx: ctx.header.material_count]),  
    "shapes" / Pointer(this.header.shape_offset, Shape[lambda ctx: ctx.header.shape_count]),  
    "samplers" / Pointer(this.header.sampler_offset, Sampler[lambda ctx: ctx.header.sampler_count]),  
      
    "positions" / Pointer(this.header.vertex_offset, Vector3[lambda ctx: ctx.header.vertex_count]),  
    "normals" / Pointer(this.header.normal_offset, Vector3[lambda ctx: ctx.header.normal_count]),  
    "colors" / Pointer(this.header.color_offset, Color8[lambda ctx: ctx.header.color_count]),  
    "texcoords" / Pointer(this.header.texcoord_offset, Vector2[lambda ctx: ctx.header.texcoord_count]),  
      
    "matrices" / Pointer(this.header.matrix_offset, Float32b[lambda ctx: 12 * ctx.header.joint_count]),  
      
    "weight_count_table" / Pointer(this.header.weight_count_table_offset, Int8ub[lambda ctx: ctx.header.weight_count]),  
    "weight_values" / Pointer(this.header.weight_offset, Float32b[lambda ctx: ctx.header.weight_count]),  
    "joint_indices" / Pointer(this.header.joint_index_offset, Int16ub[lambda ctx: ctx.header.weight_count]),  
      
    "texture_offsets" / Pointer(this.header.texture_offset_array_offset, Int32ub[lambda ctx: ctx.header.texture_count]),  
    "textures" / Array(lambda ctx: ctx.header.texture_count,   
        Pointer(lambda ctx: ctx.texture_offsets[ctx._index], Texture)  
    )  
)