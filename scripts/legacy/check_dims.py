import os
import struct


def get_png_info(filepath):
    with open(filepath, 'rb') as f:
        data = f.read(24)
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', data[16:24])
            return w, h
    return None

def main():
    dirs = ['extracted_images', 'extracted_images_2']
    for d in dirs:
        if os.path.exists(d):
            print(f"=== Directory: {d} ===")
            for f in sorted(os.listdir(d)):
                if f.endswith('.png'):
                    path = os.path.join(d, f)
                    info = get_png_info(path)
                    if info:
                        print(f"{f}: {info[0]}x{info[1]} (Size: {os.path.getsize(path)} bytes)")

if __name__ == '__main__':
    main()
