"""
回归 NszDecompressor.__getDecompressedNczSize 在插入 FakeSection 时的 size 计算。

历史 bug：当 sections[0].offset > 0x4000 时会插入 FakeSection，sections 长度
变成 sectionCount+1，但累加循环一直写的是 range(sectionCount)，会漏掉最后一段
real section，导致写进 PFS0 header 的 NCA size 比真实数据短，Ryujinx 校验
NCA hash 必然 mismatch。

修复后：循环改为 range(len(sections))，覆盖所有段。
"""
import io
import struct

from nsz import NszDecompressor

UNCOMPRESSABLE_HEADER_SIZE = 0x4000


class _StubNcz:
    """模拟一个支持 seek/read/readInt64/_path 的最小 NCZ 文件对象。

    NszDecompressor.__getDecompressedNczSize 内部只用到这几个方法，无需起一个
    完整的 BaseFile。
    """

    def __init__(self, data: bytes, path: str = "stub.ncz"):
        self.buf = io.BytesIO(data)
        self._path = path

    def seek(self, offset, whence=0):
        return self.buf.seek(offset, whence)

    def read(self, n=None):
        return self.buf.read() if n is None else self.buf.read(n)

    def readInt64(self):
        return int.from_bytes(self.buf.read(8), "little", signed=False)

    def tell(self):
        return self.buf.tell()


def _build_ncz(sections):
    """构造一个最小合法 NCZ 字节流：0x4000 头 + NCZSECTN magic + 段表。

    sections: list[(offset, size)]，按 NCZ 内 Section 表顺序排列。
    我们不需要真的塞 zstd 数据 —— size 计算只读 header 段表。
    """
    out = bytearray()
    out += b"\x00" * UNCOMPRESSABLE_HEADER_SIZE  # NCA 头占位
    out += b"NCZSECTN"
    out += len(sections).to_bytes(8, "little")
    for offset, size in sections:
        out += offset.to_bytes(8, "little")
        out += size.to_bytes(8, "little")
        out += (3).to_bytes(8, "little")  # cryptoType = 3（任意合法值）
        out += (0).to_bytes(8, "little")  # padding
        out += b"\x00" * 16               # cryptoKey
        out += b"\x00" * 16               # cryptoCounter
    return bytes(out)


def _expected_real_size(sections):
    """真实 NCA 大小 = 0x4000 + 各 section.size 之和（FakeSection 也算）。

    当 sections[0].offset == 0x4000 时无 FakeSection；否则需补一段
    [0x4000, sections[0].offset) 的 FakeSection 来覆盖中间的未压缩区。
    """
    total = UNCOMPRESSABLE_HEADER_SIZE
    if sections[0][0] > UNCOMPRESSABLE_HEADER_SIZE:
        total += sections[0][0] - UNCOMPRESSABLE_HEADER_SIZE  # FakeSection 的份
    for _, size in sections:
        total += size
    return total


def _compute_size(sections):
    ncz = _StubNcz(_build_ncz(sections))
    # 模块级名字 __getDecompressedNczSize 的双下划线在 import 时不会 mangle，
    # 直接通过属性访问即可。
    return getattr(NszDecompressor, "__getDecompressedNczSize")(ncz)


def test_no_fake_section_single_section():
    """段紧贴 0x4000 的最常见情况：不应插入 FakeSection，老/新代码都对。"""
    sections = [(0x4000, 0x10000)]
    assert _compute_size(sections) == _expected_real_size(sections) == 0x14000


def test_no_fake_section_multiple_sections():
    """多段且无 gap：不触发 FakeSection 路径。"""
    sections = [(0x4000, 0x10000), (0x14000, 0x20000)]
    expected = 0x4000 + 0x10000 + 0x20000
    assert _compute_size(sections) == _expected_real_size(sections) == expected


def test_fake_section_inserted_single_section():
    """sections[0].offset 偏离 0x4000：触发 FakeSection 插入。

    旧代码 range(sectionCount) 在 sectionCount=1 时只走 sections[0]（FakeSection），
    会漏掉那唯一的真实段，nca_size 短少 0x10000。新代码 range(len(sections))
    应覆盖到。
    """
    sections = [(0x10000, 0x10000)]
    expected = 0x10000 + 0x10000  # = sections[0].offset + sections[0].size
    assert _compute_size(sections) == _expected_real_size(sections) == expected


def test_fake_section_inserted_multiple_sections():
    """FakeSection + 多段：bug 的最痛位置 —— 末段被漏算。"""
    sections = [(0x10000, 0x10000), (0x20000, 0x20000)]
    expected = 0x20000 + 0x20000  # = sections[-1].offset + sections[-1].size
    assert _compute_size(sections) == _expected_real_size(sections) == expected
