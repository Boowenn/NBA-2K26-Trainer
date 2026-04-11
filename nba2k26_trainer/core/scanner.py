"""Memory scanning helpers for locating live player tables."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import struct
from typing import List, Optional, Tuple

from .memory import GameMemory, kernel32


MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80

READABLE_PROTECTS = (
    PAGE_READONLY,
    PAGE_READWRITE,
    PAGE_WRITECOPY,
    PAGE_EXECUTE_READ,
    PAGE_EXECUTE_READWRITE,
    PAGE_EXECUTE_WRITECOPY,
)

WRITABLE_PROTECTS = (
    PAGE_READWRITE,
    PAGE_WRITECOPY,
    PAGE_EXECUTE_READWRITE,
    PAGE_EXECUTE_WRITECOPY,
)

KNOWN_LAST_NAMES = [
    "James",
    "Curry",
    "Durant",
    "Antetokounmpo",
    "Jokic",
    "Doncic",
    "Tatum",
    "Edwards",
    "Wembanyama",
    "Morant",
    "Davis",
    "Butler",
    "Embiid",
    "Booker",
    "Mitchell",
    "Brown",
    "Young",
    "Lillard",
    "George",
    "Leonard",
]


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
    wt.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]


def parse_pattern(pattern: str) -> Tuple[bytes, bytes]:
    tokens = pattern.strip().split()
    pattern_bytes = bytearray()
    mask_bytes = bytearray()
    for token in tokens:
        if token in {"??", "?"}:
            pattern_bytes.append(0)
            mask_bytes.append(0)
        else:
            pattern_bytes.append(int(token, 16))
            mask_bytes.append(0xFF)
    return bytes(pattern_bytes), bytes(mask_bytes)


def scan_memory(mem: GameMemory, start: int, size: int, pattern: str, max_results: int = 1) -> List[int]:
    pat, mask = parse_pattern(pattern)
    pat_len = len(pat)
    results: List[int] = []

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
            if all(mask[j] == 0 or data[i + j] == pat[j] for j in range(pat_len)):
                results.append(start + offset + i)
                if len(results) >= max_results:
                    break

        offset += chunk_size

    return results


def resolve_rip_relative(mem: GameMemory, instruction_addr: int, rip_offset_pos: int = 3, instr_len: int = 7) -> Optional[int]:
    data = mem.read_bytes(instruction_addr + rip_offset_pos, 4)
    if not data or len(data) < 4:
        return None
    rip_offset = struct.unpack("<i", data)[0]
    return instruction_addr + instr_len + rip_offset


def enum_candidate_regions(
    handle: int,
    *,
    min_addr: int = 0x10000,
    max_addr: int = 0x7FFFFFFFFFFF,
    private_only: bool = True,
    writable_only: bool = True,
) -> List[Tuple[int, int, int, int]]:
    regions: List[Tuple[int, int, int, int]] = []
    addr = min_addr
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)

    allowed_protects = WRITABLE_PROTECTS if writable_only else READABLE_PROTECTS

    while addr < max_addr:
        result = kernel32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size)
        if result == 0:
            break

        base = mbi.BaseAddress or addr
        if (
            mbi.State == MEM_COMMIT
            and mbi.Protect in allowed_protects
            and mbi.RegionSize > 0
            and (not private_only or mbi.Type == MEM_PRIVATE)
        ):
            regions.append((base, mbi.RegionSize, mbi.Protect, mbi.Type))

        addr = base + mbi.RegionSize
        if addr <= base:
            break

    return regions


def enum_readable_regions(handle: int, min_addr: int = 0x10000, max_addr: int = 0x7FFFFFFFFFFF) -> List[Tuple[int, int]]:
    return [
        (base, size)
        for base, size, _, _ in enum_candidate_regions(
            handle,
            min_addr=min_addr,
            max_addr=max_addr,
            private_only=False,
            writable_only=False,
        )
    ]


def _encode_wstring(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\x00\x00"


def _is_printable_ascii(text: str) -> bool:
    return bool(text) and all(32 <= ord(char) <= 126 for char in text)


def _read_wstring_from_buf(buf: bytes, offset: int, max_chars: int) -> str:
    end = offset + max_chars * 2
    if offset < 0 or end > len(buf):
        return ""
    raw = buf[offset:end]
    try:
        text = raw.decode("utf-16-le", errors="ignore")
    except Exception:
        return ""
    null_index = text.find("\x00")
    if null_index != -1:
        text = text[:null_index]
    return text


def scan_for_player_table_candidates(
    mem: GameMemory,
    *,
    stride: int = 1176,
    last_name_offset: int = 0,
    first_name_offset: int = 40,
    name_max_chars: int = 20,
    max_players: int = 600,
    progress_callback=None,
    min_valid_records: int = 10,
    max_candidates: int = 128,
) -> List[Tuple[int, int]]:
    search_patterns = [(_name, _encode_wstring(_name)) for _name in KNOWN_LAST_NAMES[:12]]

    region_sets = [
        ("private writable", enum_candidate_regions(mem.handle, private_only=True, writable_only=True)),
        ("private readable", enum_candidate_regions(mem.handle, private_only=True, writable_only=False)),
    ]

    discovered: dict[int, int] = {}

    for label, regions in region_sets:
        if progress_callback:
            progress_callback(f"Scanning {len(regions)} {label} regions...")

        for region_base, region_size, _, _ in regions:
            if region_size < stride * 8 or region_base > 0x7FFFFFFFFFFF:
                continue

            chunk_size = min(region_size, 0x400000)
            for chunk_offset in range(0, region_size, chunk_size):
                actual_size = min(chunk_size, region_size - chunk_offset)
                chunk_addr = region_base + chunk_offset
                data = mem.read_bytes(chunk_addr, actual_size)
                if not data:
                    continue

                for _, pattern in search_patterns:
                    search_start = 0
                    while True:
                        idx = data.find(pattern, search_start)
                        if idx == -1:
                            break
                        search_start = idx + 2

                        hit_addr = chunk_addr + idx
                        record_addr = hit_addr - last_name_offset
                        first_name_in_buf = idx - last_name_offset + first_name_offset
                        if 0 <= first_name_in_buf <= len(data) - name_max_chars * 2:
                            first_name = _read_wstring_from_buf(data, first_name_in_buf, name_max_chars)
                        else:
                            first_name = mem.read_wstring(record_addr + first_name_offset, name_max_chars) or ""

                        first_name = first_name.strip()
                        if len(first_name) < 2 or not _is_printable_ascii(first_name):
                            continue

                        table_base = _find_table_start(
                            mem,
                            record_addr,
                            stride,
                            last_name_offset,
                            first_name_offset,
                            name_max_chars,
                            max_players,
                        )
                        if table_base is None:
                            continue

                        valid_count = _validate_table(
                            mem,
                            table_base,
                            stride,
                            last_name_offset,
                            first_name_offset,
                            name_max_chars,
                            min(50, max_players),
                        )
                        if valid_count < min_valid_records:
                            continue

                        previous = discovered.get(table_base, 0)
                        if valid_count > previous:
                            discovered[table_base] = valid_count
                            if progress_callback:
                                progress_callback(
                                    f"Found candidate table at 0x{table_base:X} ({valid_count} valid names)"
                                )

        if discovered:
            break

    candidates = sorted(discovered.items(), key=lambda item: item[1], reverse=True)
    return candidates[:max_candidates]


def scan_for_player_table(
    mem: GameMemory,
    stride: int = 1176,
    last_name_offset: int = 0,
    first_name_offset: int = 40,
    name_max_chars: int = 20,
    max_players: int = 600,
    progress_callback=None,
) -> Optional[int]:
    candidates = scan_for_player_table_candidates(
        mem,
        stride=stride,
        last_name_offset=last_name_offset,
        first_name_offset=first_name_offset,
        name_max_chars=name_max_chars,
        max_players=max_players,
        progress_callback=progress_callback,
    )
    return candidates[0][0] if candidates else None


def _find_table_start(
    mem: GameMemory,
    known_record: int,
    stride: int,
    last_name_offset: int,
    first_name_offset: int,
    name_max_chars: int,
    max_players: int,
) -> Optional[int]:
    current = known_record
    max_back = min(max_players, 600)

    for _ in range(max_back):
        previous = current - stride
        last = mem.read_wstring(previous + last_name_offset, name_max_chars)
        first = mem.read_wstring(previous + first_name_offset, name_max_chars)

        if last is None and first is None:
            break

        last = (last or "").strip()
        first = (first or "").strip()

        if not last and not first:
            previous2 = previous - stride
            last2 = (mem.read_wstring(previous2 + last_name_offset, name_max_chars) or "").strip()
            first2 = (mem.read_wstring(previous2 + first_name_offset, name_max_chars) or "").strip()
            if not last2 and not first2:
                break
            current = previous
            continue

        if not _is_printable_ascii(last + first):
            break

        current = previous

    return current


def _validate_table(
    mem: GameMemory,
    table_base: int,
    stride: int,
    last_name_offset: int,
    first_name_offset: int,
    name_max_chars: int,
    check_count: int,
) -> int:
    valid = 0
    for index in range(check_count):
        record = table_base + index * stride
        last = (mem.read_wstring(record + last_name_offset, name_max_chars) or "").strip()
        first = (mem.read_wstring(record + first_name_offset, name_max_chars) or "").strip()

        if not last and not first:
            continue
        if not _is_printable_ascii(last + first):
            continue
        if len(last) >= 2 or len(first) >= 2:
            valid += 1

    return valid


def scan_for_base_pointer(mem: GameMemory, table_base: int, module_base: int, image_size: int = 0x10000000) -> Optional[int]:
    target_bytes = struct.pack("<Q", table_base)
    scan_start = module_base
    scan_size = min(image_size, 0x10000000)

    results = []
    chunk_size = 0x100000
    for offset in range(0, scan_size, chunk_size):
        data = mem.read_bytes(scan_start + offset, min(chunk_size, scan_size - offset))
        if not data:
            continue

        index = 0
        while True:
            index = data.find(target_bytes, index)
            if index == -1:
                break
            found_addr = scan_start + offset + index
            results.append((found_addr, found_addr - module_base))
            index += 8

    return results[0][1] if results else None
