"""Repack the two exact dipper inputs used by the tested MIUI 9.9.3 recovery.

Uses only Python's standard library. Does not communicate with any device.
"""

import argparse
import gzip
import hashlib
import struct
import zlib
from pathlib import Path

STOCK_SHA = '1b5cfb5e59d95caa6a53afad0d44ef678835a959915cfea9824444cf2f1b03fc'
TWRP_SHA = '81239b79c90ac4342195c80bd2e9132318583a9d6601203729f4c33921b52225'
OUTPUT_SHA = 'a560e39afb94baf38b5336c27ffe8a63e45213fd45b6c7011928d222609cbcb1'


def align(size, block=4096):
    return (size + block - 1) // block * block


def checked_input(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Unexpected input SHA-256: {path}')
    return data


def boot_parts(data):
    if data[:8] != b'ANDROID!':
        raise ValueError('Not an Android boot image')
    kernel_size, _, ramdisk_size = struct.unpack_from('<3I', data, 8)
    page = struct.unpack_from('<I', data, 36)[0]
    version = struct.unpack_from('<I', data, 40)[0]
    if page != 4096 or version != 0:
        raise ValueError('Expected dipper header v0 with 4096-byte pages')
    ramdisk_start = page + align(kernel_size, page)
    return data[:page], data[page:page+kernel_size], data[ramdisk_start:ramdisk_start+ramdisk_size]


def dtb_model(data):
    fields = struct.unpack_from('>10I', data)
    magic, total, struct_start, strings_start = fields[:4]
    if magic != 0xd00dfeed or total != len(data):
        raise ValueError('Invalid FDT header')
    strings_size, struct_size = fields[8:10]
    if strings_start + strings_size > total or struct_start + struct_size > total:
        raise ValueError('Invalid FDT bounds')
    strings = data[strings_start:strings_start+strings_size]
    pos, depth = struct_start, 0
    while pos < struct_start + struct_size:
        token = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if token == 1:  # FDT_BEGIN_NODE
            end = data.index(0, pos)
            pos = align(end + 1, 4)
            depth += 1
        elif token == 2:  # FDT_END_NODE
            depth -= 1
        elif token == 3:  # FDT_PROP
            size, nameoff = struct.unpack_from('>2I', data, pos)
            pos += 8
            name = strings[nameoff:strings.index(0, nameoff)]
            if depth == 1 and name == b'model':
                return data[pos:pos+size].rstrip(b'\0').decode()
            pos = align(pos + size, 4)
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            break
        else:
            raise ValueError(f'Unexpected FDT token: {token}')
    return ''


def dipper_kernel(kernel):
    inflater = zlib.decompressobj(31)
    inflater.decompress(kernel)
    if not inflater.eof:
        raise ValueError('Invalid gzip-compressed kernel')
    offset = len(kernel) - len(inflater.unused_data)
    compressed_kernel = kernel[:offset]
    selected = []
    while offset < len(kernel):
        magic, size = struct.unpack_from('>2I', kernel, offset)
        if magic != 0xd00dfeed or size < 40 or offset + size > len(kernel):
            raise ValueError(f'Invalid appended DTB at {offset}')
        dtb = kernel[offset:offset+size]
        model = dtb_model(dtb)
        if 'Dipper' in model:
            selected.append(dtb)
            print(f'Keeping: {model}')
        offset += size
    if len(selected) != 22:
        raise ValueError(f'Expected 22 Dipper DTBs, got {len(selected)}')
    return compressed_kernel + b''.join(selected)


def cpio_records(blob):
    offset = 0
    while True:
        start = offset
        header = blob[offset:offset+110]
        if header[:6] != b'070701':
            raise ValueError(f'Unsupported cpio header at {offset}')
        fields = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        name = blob[offset+110:offset+110+namesize-1].decode()
        payload = align(offset+110+namesize, 4)
        offset = align(payload+size, 4)
        yield name, header, blob[start+110:payload], blob[payload:payload+size], blob[start:offset]
        if name == 'TRAILER!!!':
            return


def patch_ramdisk(ramdisk):
    original = list(cpio_records(gzip.decompress(ramdisk)))
    output, changed = bytearray(), []
    for name, header, namepart, data, entry in original:
        if name == 'prop.default':
            if data.count(b'ro.build.version.release=16.1.0\n') != 1:
                raise ValueError('Unexpected Android release property')
            if data.count(b'ro.build.version.security_patch=2099-12-31\n') != 1:
                raise ValueError('Unexpected security patch property')
            new = data.replace(b'ro.build.version.release=16.1.0\n', b'ro.build.version.release=9\n')
            new = new.replace(b'ro.build.version.security_patch=2099-12-31\n', b'ro.build.version.security_patch=2019-09-01\n')
            new_header = header[:54] + f'{len(new):08x}'.encode() + header[62:]
            output.extend(new_header + namepart + new + b'\0' * (-len(new) % 4))
            changed.append(name)
        else:
            output.extend(entry)
    if changed != ['prop.default']:
        raise ValueError(f'Unexpected changed entries: {changed}')
    output.extend(b'\0' * (-len(output) % 512))
    after = list(cpio_records(output))
    if len(after) != len(original):
        raise ValueError('CPIO member count changed')
    for old, new in zip(original, after):
        if old[0] != new[0] or (old[0] != 'prop.default' and old[4] != new[4]):
            raise ValueError('Unintended ramdisk change')
    return gzip.compress(bytes(output), compresslevel=9, mtime=0)


def build_image(template, kernel, ramdisk):
    header = bytearray(template)
    struct.pack_into('<I', header, 8, len(kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    struct.pack_into('<2I', header, 24, 0, 0)  # no second-stage image
    os_version = (9 << 25) | ((2019-2000) << 4) | 9
    struct.pack_into('<I', header, 44, os_version)
    digest = hashlib.sha1()
    for part in (kernel, ramdisk, b''):
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    header[576:608] = digest.digest() + b'\0' * 12
    image = bytes(header) + kernel + b'\0' * (-len(kernel) % 4096)
    image += ramdisk + b'\0' * (-len(ramdisk) % 4096)
    if len(image) > 67108864:
        raise ValueError('Image exceeds the 64 MiB recovery partition')
    _, check_kernel, check_ramdisk = boot_parts(image)
    if check_kernel != kernel or check_ramdisk != ramdisk:
        raise ValueError('Output boot image verification failed')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-recovery', required=True)
    parser.add_argument('--twrp', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output_path = Path(args.output)
    if output_path.exists():
        raise FileExistsError(f'Refusing to overwrite: {output_path}')
    _, stock_kernel, _ = boot_parts(checked_input(args.stock_recovery, STOCK_SHA))
    header, _, ramdisk = boot_parts(checked_input(args.twrp, TWRP_SHA))
    image = build_image(header, dipper_kernel(stock_kernel), patch_ramdisk(ramdisk))
    output_path.write_bytes(image)
    digest = hashlib.sha256(image).hexdigest()
    print(f'Size: {len(image)} bytes')
    print(f'SHA-256: {digest}')
    print(f'Matches tested release: {digest == OUTPUT_SHA}')


if __name__ == '__main__':
    main()
