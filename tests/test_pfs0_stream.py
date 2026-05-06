"""
回归 Pfs0Stream（写流）的两个点：

1. getFirstFileOffset() 之前写的是 self.files[0].offset，但 files 是 dict 列表，
   属性访问会 AttributeError。改成 self.files[0]['offset'] 后必须能正常返回 int。

2. 写出来的 PFS0 文件能被 Pfs0（读流）反向解析回相同的文件名 / 大小 / offset
   —— 也就是 header roundtrip。
"""
import struct
from pathlib import Path

from nsz.Fs import Pfs0


PFS0_HEADER_BASE = 0x10  # magic(4) + fileCount(4) + stringTableSize(4) + junk(4)
PFS0_FILE_ENTRY = 0x18   # offset(8) + size(8) + nameOffset(4) + junk(4)


def _write_pfs0(tmp_path: Path, files):
    """用 Pfs0Stream 写一个最小 PFS0 容器。

    files: list[(name, payload_bytes)]
    返回写完的文件路径。
    """
    out = tmp_path / "out.pfs0"
    # headerSize / stringTableSize 都用 None 让 Pfs0Stream 自己算（fix-padding 路径）
    stream = Pfs0.Pfs0Stream(0, None, str(out))
    # Pfs0Stream 构造时按传入 headerSize 设了 addpos；这里我们用 None 走"按需扩展"模式：
    # 直接调 add() 时 stream.headerSize 影响第一个文件的预期 offset，构造起来麻烦。
    # 改为先估好 headerSize 再重建一个干净的 stream。
    stream.close()
    if out.exists():
        out.unlink()

    # 估算 headerSize（必须 0x20 对齐才能完整复刻 fix-padding 模式）
    string_table = b"\x00".join(name.encode() for name, _ in files) + b"\x00"
    raw_header = PFS0_HEADER_BASE + PFS0_FILE_ENTRY * len(files) + len(string_table)
    pad = (-raw_header) % 0x20
    header_size = raw_header + pad

    # 真正写入
    stream = Pfs0.Pfs0Stream(header_size, None, str(out))
    for name, payload in files:
        partition = stream.add(name, len(payload))
        partition.write(payload)
    stream.close()
    return out


def _parse_pfs0(path: Path):
    """直接二进制解析 PFS0，避免依赖 Pfs0.open 里的 Fs.factory（factory 对
    .nca 等扩展会试图加载 keys）。返回 (file_count, [(name, offset, size)])。
    """
    data = path.read_bytes()
    assert data[:4] == b"PFS0", f"bad magic: {data[:4]!r}"
    file_count = struct.unpack_from("<I", data, 4)[0]
    string_table_size = struct.unpack_from("<I", data, 8)[0]

    table_start = PFS0_HEADER_BASE
    string_table_start = table_start + PFS0_FILE_ENTRY * file_count
    string_table = data[string_table_start:string_table_start + string_table_size]
    header_size = string_table_start + string_table_size

    files = []
    for i in range(file_count):
        base = table_start + PFS0_FILE_ENTRY * i
        offset, size, name_offset, _junk = struct.unpack_from("<QQII", data, base)
        # 字符串表里以 \0 分隔，从 nameOffset 起截到下一个 \0
        end = string_table.find(b"\x00", name_offset)
        if end == -1:
            end = len(string_table)
        name = string_table[name_offset:end].decode("utf-8")
        files.append((name, offset, size))
    return file_count, files, header_size, data


def test_roundtrip_minimal_pfs0(tmp_path):
    """三个文件、内容长度互异：写 -> 解析回来文件表完全一致。"""
    files = [
        ("aaaa.bin", b"A" * 0x10),
        ("b.bin",    b"B" * 0x33),
        ("ccc.bin",  b"C" * 0x100),
    ]
    out = _write_pfs0(tmp_path, files)

    file_count, parsed, header_size, raw = _parse_pfs0(out)
    assert file_count == len(files)

    expected_offset = 0
    for (orig_name, orig_payload), (got_name, got_offset, got_size) in zip(files, parsed):
        assert got_name == orig_name
        assert got_size == len(orig_payload)
        assert got_offset == expected_offset, "PFS0 file table 应记录连续紧凑布局"
        # 真实数据按 offset+headerSize 取出来，应该等于原始 payload
        abs_start = header_size + got_offset
        assert raw[abs_start:abs_start + got_size] == orig_payload
        expected_offset += got_size


def test_get_first_file_offset_returns_int(tmp_path):
    """这是 Pfs0.py 里改动那行（self.files[0].offset → self.files[0]['offset']）
    的最小回归用例：files 是 dict 列表，属性式访问会 AttributeError。
    """
    out = tmp_path / "x.pfs0"
    files = [("a.bin", 16), ("b.bin", 32)]

    # headerSize 必须能被 getHeader() 重算后的同名值精确等价，否则
    # close() 时算 (offset - headerSize) 会负数溢出。这里复刻 fix-padding 的算法。
    string_table = b"\x00".join(name.encode() for name, _ in files) + b"\x00"
    raw = 0x10 + 0x18 * len(files) + len(string_table)
    header_size = raw + (-raw) % 0x20

    stream = Pfs0.Pfs0Stream(header_size, None, str(out))
    for name, size in files:
        stream.add(name, size)

    first_offset = stream.getFirstFileOffset()
    assert isinstance(first_offset, int)
    assert first_offset == header_size  # 第一个文件应紧跟 PFS0 header

    # 真正写盘 + close（就让 stream 的字节流走完，确保改动在 close path 下也安全）
    stream.f.seek(stream.headerSize)
    for name, size in files:
        partition = stream.get(name)
        partition.write(b"\xab" * size)
    stream.close()
