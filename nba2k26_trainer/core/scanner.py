"""特征码扫描 - AOB (Array of Bytes) 模式搜索"""

import re
from typing import Optional, List

from .memory import GameMemory


def parse_pattern(pattern: str) -> tuple[bytes, bytes]:
    """解析特征码字符串为 (pattern_bytes, mask_bytes)

    例如: "48 8B 05 ?? ?? ?? ?? 48 8B 48 08"
    ?? 表示通配符
    """
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
    """在内存范围内搜索特征码

    Args:
        mem: GameMemory 实例
        start: 起始地址
        size: 扫描范围大小
        pattern: 特征码字符串 (如 "48 8B 05 ?? ?? ?? ??")
        max_results: 最大结果数

    Returns:
        匹配地址列表
    """
    pat, mask = parse_pattern(pattern)
    pat_len = len(pat)
    results = []

    chunk_size = 0x10000  # 64KB per read
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
    """解析 RIP 相对寻址指令，获取目标绝对地址

    常见于 x64: MOV RAX, [RIP+offset] = 48 8B 05 xx xx xx xx
    """
    data = mem.read_bytes(instruction_addr + rip_offset_pos, 4)
    if not data or len(data) < 4:
        return None
    import struct
    rip_offset = struct.unpack("<i", data)[0]
    return instruction_addr + instr_len + rip_offset
