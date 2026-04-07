"""特征码扫描 + 动态球员表定位"""

import ctypes
import ctypes.wintypes as wt
import struct
from typing import Optional, List

from .memory import GameMemory, kernel32


# ============================================================
# AOB Pattern Scanning
# ============================================================

def parse_pattern(pattern: str) -> tuple[bytes, bytes]:
    """解析特征码字符串为 (pattern_bytes, mask_bytes)"""
    tokens = pattern.strip().split()
    pattern_bytes = bytearray()
    mask_bytes = bytearray()
    for token in tokens:
        if token == "??" or token == "?":
            pattern_bytes.append(0)
            mask_bytes.append(0)
        else:
            pattern_bytes.append(int(token, 16))
            mask_bytes.append(0xFF)
    return bytes(pattern_bytes), bytes(mask_bytes)


def scan_memory(mem: GameMemory, start: int, size: int,
                pattern: str, max_results: int = 1) -> List[int]:
    """在内存范围内搜索特征码"""
    pat, mask = parse_pattern(pattern)
    pat_len = len(pat)
    results = []

    chunk_size = 0x10000
    overlap = pat_len - 1

    offset = 0
    while offset < size and len(results) < max_results:
        read_size = min(chunk_size + overlap, size - offset)
        data = mem.read_bytes(start + offset, read_size)
        if not data:
            offset += chunk_size
            continue

        for i in range(len(data) - pat_len + 1):
            match = True
            for j in range(pat_len):
                if mask[j] != 0 and data[i + j] != pat[j]:
                    match = False
                    break
            if match:
                addr = start + offset + i
                results.append(addr)
                if len(results) >= max_results:
                    break

        offset += chunk_size

    return results


def resolve_rip_relative(mem: GameMemory, instruction_addr: int,
                          rip_offset_pos: int = 3, instr_len: int = 7) -> Optional[int]:
    """解析 RIP 相对寻址指令"""
    data = mem.read_bytes(instruction_addr + rip_offset_pos, 4)
    if not data or len(data) < 4:
        return None
    rip_offset = struct.unpack("<i", data)[0]
    return instruction_addr + instr_len + rip_offset


# ============================================================
# VirtualQueryEx for memory region enumeration
# ============================================================

MEM_COMMIT = 0x1000
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80

READABLE_PROTECTS = (
    PAGE_READONLY, PAGE_READWRITE, PAGE_WRITECOPY,
    PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY,
)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("PartitionId", wt.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.VirtualQueryEx.argtypes = [
    wt.HANDLE, ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
]


def enum_readable_regions(handle: int,
                           min_addr: int = 0x10000,
                           max_addr: int = 0x7FFFFFFFFFFF) -> List[tuple]:
    """枚举进程中所有可读的已提交内存区域"""
    regions = []
    addr = min_addr
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)

    while addr < max_addr:
        result = kernel32.VirtualQueryEx(
            handle, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size
        )
        if result == 0:
            break

        if (mbi.State == MEM_COMMIT and
                mbi.Protect in READABLE_PROTECTS and
                mbi.RegionSize > 0):
            base = mbi.BaseAddress if mbi.BaseAddress else addr
            regions.append((base, mbi.RegionSize))

        addr = (mbi.BaseAddress or addr) + mbi.RegionSize
        if addr <= (mbi.BaseAddress or 0):
            break

    return regions


# ============================================================
# Dynamic Player Table Scanner
# ============================================================

# Well-known player names that should exist in any NBA 2K26 roster
# Using last names since they're at offset 0 in the record
KNOWN_LAST_NAMES = [
    "James", "Curry", "Durant", "Antetokounmpo", "Jokic",
    "Doncic", "Tatum", "Edwards", "Wembanyama", "Morant",
    "Davis", "Butler", "Embiid", "Booker", "Mitchell",
    "Brown", "Young", "Lillard", "George", "Leonard",
]

KNOWN_FIRST_NAMES = [
    "LeBron", "Stephen", "Kevin", "Giannis", "Nikola",
    "Luka", "Jayson", "Anthony", "Victor", "Ja",
]


def _encode_wstring(text: str) -> bytes:
    """Encode string as UTF-16LE with null terminator"""
    return text.encode("utf-16-le") + b"\x00\x00"


def _is_printable_ascii(text: str) -> bool:
    """Check if string contains only printable ASCII"""
    return all(32 <= ord(c) <= 126 for c in text)


def _read_wstring_from_buf(buf: bytes, offset: int, max_chars: int) -> str:
    """Read a wstring from a buffer"""
    byte_len = max_chars * 2
    end = offset + byte_len
    if end > len(buf):
        return ""
    raw = buf[offset:end]
    try:
        text = raw.decode("utf-16-le", errors="ignore")
    except Exception:
        return ""
    null = text.find("\x00")
    if null != -1:
        text = text[:null]
    return text


def scan_for_player_table(mem: GameMemory,
                           stride: int = 1176,
                           last_name_offset: int = 0,
                           first_name_offset: int = 40,
                           name_max_chars: int = 20,
                           max_players: int = 600,
                           progress_callback=None) -> Optional[int]:
    """动态扫描内存寻找球员表基地址

    Strategy:
    1. Search all readable memory for UTF-16LE encoded known player last names
    2. For each hit, check if it aligns as a player record (valid first name at offset 40)
    3. Walk backwards to find the table start
    4. Validate by checking multiple records at the expected stride

    Returns: table base address, or None if not found
    """
    # Build search patterns for last names
    search_patterns = []
    for name in KNOWN_LAST_NAMES[:10]:  # Use top 10
        pattern = _encode_wstring(name)
        search_patterns.append((name, pattern))

    # Get readable memory regions
    regions = enum_readable_regions(mem.handle)
    if progress_callback:
        progress_callback(f"Scanning {len(regions)} memory regions...")

    candidates = []  # (table_base, valid_count)

    for region_idx, (region_base, region_size) in enumerate(regions):
        # Skip tiny regions and kernel-space-looking addresses
        if region_size < stride * 10:
            continue
        if region_base > 0x7FFFFFFFFFFF:
            continue

        # Read region in chunks
        chunk_size = min(region_size, 0x400000)  # 4MB chunks
        for chunk_offset in range(0, region_size, chunk_size):
            actual_size = min(chunk_size, region_size - chunk_offset)
            chunk_addr = region_base + chunk_offset
            data = mem.read_bytes(chunk_addr, actual_size)
            if not data:
                continue

            # Search for each known name in this chunk
            for name, pattern in search_patterns:
                pat_len = len(pattern)
                search_start = 0
                while True:
                    idx = data.find(pattern, search_start)
                    if idx == -1:
                        break
                    search_start = idx + 2  # Move past for next search

                    # Found a name match at chunk_addr + idx
                    hit_addr = chunk_addr + idx

                    # Check if this could be a last_name field (at last_name_offset from record start)
                    record_addr = hit_addr - last_name_offset

                    # Verify: read first name from the same record
                    first_name_addr = record_addr + first_name_offset
                    first_name_in_buf = idx - last_name_offset + first_name_offset
                    if 0 <= first_name_in_buf < len(data) - name_max_chars * 2:
                        first = _read_wstring_from_buf(data, first_name_in_buf, name_max_chars)
                    else:
                        first = mem.read_wstring(first_name_addr, name_max_chars)
                        if first is None:
                            continue

                    first = first.strip()
                    if not first or not _is_printable_ascii(first):
                        continue
                    if len(first) < 2:
                        continue

                    # This looks like a valid player record!
                    # Now find the table base by walking backwards
                    table_base = _find_table_start(
                        mem, record_addr, stride,
                        last_name_offset, first_name_offset,
                        name_max_chars, max_players
                    )
                    if table_base is not None:
                        # Validate the table base
                        valid_count = _validate_table(
                            mem, table_base, stride,
                            last_name_offset, first_name_offset,
                            name_max_chars, min(50, max_players)
                        )
                        if valid_count >= 10:
                            candidates.append((table_base, valid_count))
                            if progress_callback:
                                progress_callback(
                                    f"Found candidate table at 0x{table_base:X} "
                                    f"({valid_count} valid players)"
                                )

                    # Don't search more occurrences of this name
                    break

        # Early exit if we found a good candidate
        if candidates and candidates[-1][1] >= 30:
            break

    if not candidates:
        return None

    # Return the candidate with the most valid players
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def _find_table_start(mem: GameMemory, known_record: int, stride: int,
                       last_name_offset: int, first_name_offset: int,
                       name_max_chars: int, max_players: int) -> Optional[int]:
    """从已知的球员记录地址向前回溯，找到球员表起始位置"""
    # Walk backwards from known record
    current = known_record
    max_back = min(max_players, 600)

    for step in range(max_back):
        prev = current - stride
        # Check if previous record has a valid name
        last = mem.read_wstring(prev + last_name_offset, name_max_chars)
        first = mem.read_wstring(prev + first_name_offset, name_max_chars)

        if last is None and first is None:
            # Can't read memory - we've gone too far
            break

        last = (last or "").strip()
        first = (first or "").strip()

        if not last and not first:
            # Empty record - might be start of table or gap
            # Check one more back
            prev2 = prev - stride
            last2 = mem.read_wstring(prev2 + last_name_offset, name_max_chars)
            first2 = mem.read_wstring(prev2 + first_name_offset, name_max_chars)
            last2 = (last2 or "").strip()
            first2 = (first2 or "").strip()
            if not last2 and not first2:
                # Two empty records - this is likely the start
                break
            # Single gap, keep going
            current = prev
            continue

        if not _is_printable_ascii(last + first):
            break

        current = prev

    return current


def _validate_table(mem: GameMemory, table_base: int, stride: int,
                     last_name_offset: int, first_name_offset: int,
                     name_max_chars: int, check_count: int) -> int:
    """验证球员表：统计有效球员记录数量"""
    valid = 0
    for i in range(check_count):
        record = table_base + i * stride
        last = mem.read_wstring(record + last_name_offset, name_max_chars)
        first = mem.read_wstring(record + first_name_offset, name_max_chars)

        last = (last or "").strip()
        first = (first or "").strip()

        if not last and not first:
            continue

        if not _is_printable_ascii(last + first):
            continue

        if len(last) >= 2 or len(first) >= 2:
            valid += 1

    return valid


def scan_for_base_pointer(mem: GameMemory, table_base: int,
                           module_base: int, image_size: int = 0x10000000) -> Optional[int]:
    """找到球员表基地址后，反向搜索指向该地址的指针（用于更新配置）

    在模块的 .data/.rdata 段中搜索存储了 table_base 值的地址
    """
    target_bytes = struct.pack("<Q", table_base)

    # Scan the module's data sections (typically after .text)
    # Start from module_base + some offset to skip code section
    scan_start = module_base
    scan_size = min(image_size, 0x10000000)  # Cap at 256MB

    results = []
    chunk_size = 0x100000  # 1MB
    for offset in range(0, scan_size, chunk_size):
        data = mem.read_bytes(scan_start + offset, min(chunk_size, scan_size - offset))
        if not data:
            continue
        idx = 0
        while True:
            idx = data.find(target_bytes, idx)
            if idx == -1:
                break
            found_addr = scan_start + offset + idx
            rva = found_addr - module_base
            results.append((found_addr, rva))
            idx += 8

    return results[0][1] if results else None  # Return RVA
