"""特征码扫描 + 动态球员表定位"""

import ctypes
import ctypes.wintypes as wt
import struct
from typing import Optional, List, Tuple

from .memory import GameMemory, kernel32


# ============================================================
# VirtualQueryEx for memory region enumeration
# ============================================================

MEM_COMMIT = 0x1000
MEM_IMAGE = 0x1000000
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
            regions.append((base, mbi.RegionSize, mbi.Type))

        addr = (mbi.BaseAddress or addr) + mbi.RegionSize
        if addr <= (mbi.BaseAddress or 0):
            break

    return regions


# ============================================================
# Helpers
# ============================================================

def _read_wstring_safe(mem: GameMemory, address: int, max_chars: int) -> str:
    """Read wstring with proper null termination"""
    data = mem.read_bytes(address, max_chars * 2)
    if not data:
        return ""
    for i in range(0, len(data) - 1, 2):
        if data[i] == 0 and data[i + 1] == 0:
            data = data[:i]
            break
    try:
        return data.decode("utf-16-le", errors="ignore").strip()
    except Exception:
        return ""


def _is_ascii_name(text: str) -> bool:
    """Check if string looks like a real player name (ASCII letters, spaces, etc)"""
    if not text or len(text) < 2:
        return False
    for c in text:
        o = ord(c)
        if o < 32 or o > 126:
            return False
    # Must contain at least one letter
    return any(c.isalpha() for c in text)


def _validate_as_player_table(mem: GameMemory, base: int, stride: int,
                                last_name_off: int, first_name_off: int,
                                name_chars: int, ovr_offset: int,
                                check_count: int) -> Tuple[int, int]:
    """Validate a candidate player table base.
    Returns (valid_name_count, valid_ovr_count)"""
    valid_names = 0
    valid_ovr = 0
    for i in range(check_count):
        rec = base + i * stride
        last = _read_wstring_safe(mem, rec + last_name_off, name_chars)
        first = _read_wstring_safe(mem, rec + first_name_off, name_chars)

        if not _is_ascii_name(last) or not _is_ascii_name(first):
            continue
        valid_names += 1

        # Check OVR is in sane range (25-99 for real players)
        ovr = mem.read_uint8(rec + ovr_offset)
        if ovr is not None and 25 <= ovr <= 99:
            valid_ovr += 1

    return valid_names, valid_ovr


# ============================================================
# Method 1: Pointer Table Scan
# Scan the game's .data section for pointers to valid player tables
# ============================================================

def scan_pointer_table(mem: GameMemory,
                        module_base: int,
                        stride: int = 1176,
                        last_name_off: int = 0,
                        first_name_off: int = 40,
                        name_chars: int = 20,
                        ovr_offset: int = 61,
                        progress_callback=None) -> Optional[int]:
    """Scan the game module's data sections for a pointer to the player table.

    The game stores a pointer to the player table somewhere in its .data section.
    We scan every 8-byte aligned uint64 in the module image, and for each value
    that looks like a valid heap pointer, we check if it points to a player table.
    """
    regions = enum_readable_regions(mem.handle)

    # Find regions that belong to the main module image
    # (AllocationBase == module_base, Type == MEM_IMAGE)
    module_regions = []
    for base, size, mtype in regions:
        if mtype == MEM_IMAGE and base >= module_base and base < module_base + 0x20000000:
            module_regions.append((base, size))

    if not module_regions and progress_callback:
        progress_callback(f"No module regions found at base 0x{module_base:X}, trying all regions...")

    # If no image regions found, try scanning near the module base
    if not module_regions:
        for base, size, mtype in regions:
            if module_base <= base < module_base + 0x20000000:
                module_regions.append((base, size))

    total_size = sum(s for _, s in module_regions)
    if progress_callback:
        progress_callback(f"Scanning {len(module_regions)} module regions ({total_size // 1024 // 1024}MB) for player table pointer...")

    best_candidate = None
    best_score = 0

    scanned = 0
    for region_base, region_size in module_regions:
        # Read the region in chunks
        chunk_size = 0x100000  # 1MB
        for offset in range(0, region_size, chunk_size):
            read_size = min(chunk_size, region_size - offset)
            addr = region_base + offset
            data = mem.read_bytes(addr, read_size)
            if not data:
                continue

            scanned += read_size

            # Scan for uint64 values that look like heap pointers
            for i in range(0, len(data) - 7, 8):
                ptr = struct.unpack_from("<Q", data, i)[0]

                # Must look like a valid pointer (in user-space heap range)
                if ptr < 0x10000 or ptr > 0x7FFFFFFFFFFF:
                    continue
                # Skip pointers into the module itself (those are code/data, not heap)
                if module_base <= ptr < module_base + 0x20000000:
                    continue

                # Quick check: can we read at this address?
                test = mem.read_bytes(ptr, 4)
                if not test:
                    continue

                # Check if this pointer leads to a player table
                names, ovrs = _validate_as_player_table(
                    mem, ptr, stride, last_name_off, first_name_off,
                    name_chars, ovr_offset, 10
                )

                if names >= 5 and ovrs >= 3:
                    # Promising! Do a deeper check
                    names2, ovrs2 = _validate_as_player_table(
                        mem, ptr, stride, last_name_off, first_name_off,
                        name_chars, ovr_offset, 50
                    )
                    score = names2 + ovrs2
                    rva = (addr + i) - module_base
                    if progress_callback:
                        progress_callback(
                            f"Candidate at RVA 0x{rva:X}: ptr=0x{ptr:X}, "
                            f"{names2} names, {ovrs2} valid OVR"
                        )
                    if score > best_score:
                        best_score = score
                        best_candidate = ptr
                        # If we found a really good match, stop early
                        if names2 >= 30 and ovrs2 >= 20:
                            if progress_callback:
                                progress_callback(
                                    f"Found player table at 0x{ptr:X} "
                                    f"(RVA 0x{rva:X}, {names2} names, {ovrs2} OVR)"
                                )
                            return best_candidate

            if progress_callback and scanned % (chunk_size * 10) == 0:
                pct = scanned * 100 // max(total_size, 1)
                progress_callback(f"Scanning module data... {pct}%")

    return best_candidate


# ============================================================
# Method 2: Name-based scan (fallback)
# Search all memory for known player name pairs
# ============================================================

# Known player name PAIRS (last, first) - must match to avoid false positives
KNOWN_PLAYERS = [
    ("James", "LeBron"),
    ("Curry", "Stephen"),
    ("Durant", "Kevin"),
    ("Jokic", "Nikola"),
    ("Doncic", "Luka"),
    ("Tatum", "Jayson"),
    ("Wembanyama", "Victor"),
    ("Antetokounmpo", "Giannis"),
    ("Edwards", "Anthony"),
    ("Embiid", "Joel"),
    ("Davis", "Anthony"),
    ("Booker", "Devin"),
    ("Morant", "Ja"),
    ("Butler", "Jimmy"),
    ("Lillard", "Damian"),
]


def scan_for_player_table(mem: GameMemory,
                           stride: int = 1176,
                           last_name_offset: int = 0,
                           first_name_offset: int = 40,
                           name_max_chars: int = 20,
                           max_players: int = 600,
                           ovr_offset: int = 61,
                           progress_callback=None) -> Optional[int]:
    """Search all readable memory for known player name pairs.
    Much stricter than before - requires matching first+last name pair.
    """
    regions = enum_readable_regions(mem.handle)
    if progress_callback:
        progress_callback(f"Name scan: {len(regions)} memory regions...")

    best_candidate = None
    best_score = 0

    for last_name, first_name in KNOWN_PLAYERS[:8]:
        pattern = last_name.encode("utf-16-le")

        for region_base, region_size, _ in regions:
            if region_size < stride * 10:
                continue

            chunk_size = min(region_size, 0x400000)
            for chunk_off in range(0, region_size, chunk_size):
                actual = min(chunk_size, region_size - chunk_off)
                chunk_addr = region_base + chunk_off
                data = mem.read_bytes(chunk_addr, actual)
                if not data:
                    continue

                search_pos = 0
                while True:
                    idx = data.find(pattern, search_pos)
                    if idx == -1:
                        break
                    search_pos = idx + 2

                    hit_addr = chunk_addr + idx
                    record_addr = hit_addr - last_name_offset

                    # Must have the matching first name at first_name_offset
                    first_read = _read_wstring_safe(mem, record_addr + first_name_offset, name_max_chars)
                    if first_read != first_name:
                        continue

                    # MATCHED a known player name pair!
                    if progress_callback:
                        progress_callback(f"Found {first_name} {last_name} at 0x{record_addr:X}")

                    # Walk back to find table start
                    table_base = record_addr
                    for _ in range(max_players):
                        prev = table_base - stride
                        pl = _read_wstring_safe(mem, prev + last_name_offset, name_max_chars)
                        pf = _read_wstring_safe(mem, prev + first_name_offset, name_max_chars)
                        if not _is_ascii_name(pl) and not _is_ascii_name(pf):
                            # Check one more back
                            pl2 = _read_wstring_safe(mem, prev - stride + last_name_offset, name_max_chars)
                            if not _is_ascii_name(pl2):
                                break
                        table_base = prev

                    # Validate with OVR check
                    names, ovrs = _validate_as_player_table(
                        mem, table_base, stride, last_name_offset,
                        first_name_offset, name_max_chars, ovr_offset, 50
                    )
                    score = names + ovrs

                    if progress_callback:
                        progress_callback(
                            f"Table at 0x{table_base:X}: {names} names, {ovrs} valid OVR"
                        )

                    if score > best_score and names >= 10 and ovrs >= 5:
                        best_score = score
                        best_candidate = table_base

                    if best_score >= 60:
                        return best_candidate

                    break  # Don't search more occurrences

        if best_score >= 40:
            break

    return best_candidate


# ============================================================
# Combined scan: try all methods
# ============================================================

def find_player_table(mem: GameMemory,
                       module_base: int,
                       stride: int = 1176,
                       last_name_off: int = 0,
                       first_name_off: int = 40,
                       name_chars: int = 20,
                       ovr_offset: int = 61,
                       max_players: int = 600,
                       progress_callback=None) -> Optional[int]:
    """Combined player table search using multiple methods.

    1. First: scan module data sections for a pointer to the player table (fastest, most reliable)
    2. Fallback: search all memory for known player name pairs
    """
    # Method 1: Pointer scan in module
    if progress_callback:
        progress_callback("Method 1: Scanning module for player table pointer...")
    result = scan_pointer_table(
        mem, module_base, stride, last_name_off, first_name_off,
        name_chars, ovr_offset, progress_callback
    )
    if result:
        return result

    # Method 2: Name pair scan
    if progress_callback:
        progress_callback("Method 2: Searching for known player names...")
    result = scan_for_player_table(
        mem, stride, last_name_off, first_name_off, name_chars,
        max_players, ovr_offset, progress_callback
    )
    if result:
        return result

    if progress_callback:
        progress_callback("All scan methods failed.")
    return None


def scan_for_base_pointer(mem: GameMemory, table_base: int,
                           module_base: int, image_size: int = 0x10000000) -> Optional[int]:
    """Find the RVA of a pointer to table_base within the module image."""
    target_bytes = struct.pack("<Q", table_base)
    scan_size = min(image_size, 0x10000000)

    chunk_size = 0x100000
    for offset in range(0, scan_size, chunk_size):
        data = mem.read_bytes(module_base + offset, min(chunk_size, scan_size - offset))
        if not data:
            continue
        idx = data.find(target_bytes)
        if idx != -1:
            return offset + idx  # Return RVA

    return None
