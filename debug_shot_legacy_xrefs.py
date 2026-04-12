"""Scan live NBA2K26.exe xrefs for legacy shot-state field offsets."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from nba2k26_trainer.core.process import attach_to_game


IMAGE_SCN_MEM_EXECUTE = 0x20000000
CHUNK_SIZE = 0x200000
OVERLAP = 0x20

FIELD_TARGETS = {
    0x450: "LegacyStateClusterA",
    0x452: "LegacyStateClusterAFlags",
    0xBF0: "LegacyStateClusterB",
    0xBF2: "LegacyStateClusterBFlags",
    0x200: "LegacyFloatPairA",
    0x870: "LegacyFloatPairB",
    0x9A0: "LegacyFloatPairAMirror",
    0x1010: "LegacyFloatPairBMirror",
}


@dataclass(slots=True)
class Section:
    name: str
    address: int
    size: int
    characteristics: int


def _iter_executable_sections(mem) -> Iterable[Section]:
    module_base = int(mem.base_address or 0)
    pe_header_offset = mem.read_uint32(module_base + 0x3C)
    if not isinstance(pe_header_offset, int) or pe_header_offset <= 0:
        return []

    number_of_sections = mem.read_uint16(module_base + pe_header_offset + 6)
    size_of_optional_header = mem.read_uint16(module_base + pe_header_offset + 20)
    if not isinstance(number_of_sections, int) or not isinstance(size_of_optional_header, int):
        return []

    section_base = module_base + pe_header_offset + 24 + size_of_optional_header
    sections: list[Section] = []

    for index in range(number_of_sections):
        header = section_base + index * 40
        name_bytes = mem.read_bytes(header, 8) or b""
        name = name_bytes.split(b"\x00")[0].decode("ascii", errors="ignore")
        virtual_size = int(mem.read_uint32(header + 8) or 0)
        virtual_address = int(mem.read_uint32(header + 12) or 0)
        raw_size = int(mem.read_uint32(header + 16) or 0)
        characteristics = int(mem.read_uint32(header + 36) or 0)
        size = max(virtual_size, raw_size)
        if size <= 0 or not (characteristics & IMAGE_SCN_MEM_EXECUTE):
            continue
        sections.append(
            Section(
                name=name,
                address=module_base + virtual_address,
                size=size,
                characteristics=characteristics,
            )
        )

    return sections


def _iter_section_chunks(mem, section: Section):
    offset = 0
    while offset < section.size:
        read_size = min(CHUNK_SIZE + OVERLAP, section.size - offset)
        blob = mem.read_bytes(section.address + offset, read_size)
        if blob:
            yield section.address + offset, blob
        offset += CHUNK_SIZE


def _scan_field_hits(mem, section: Section):
    patterns = {value: struct.pack("<I", value) for value in FIELD_TARGETS}
    for chunk_base, blob in _iter_section_chunks(mem, section):
        for target_value, pattern in patterns.items():
            start = 0
            while True:
                index = blob.find(pattern, start)
                if index == -1:
                    break
                yield target_value, chunk_base + index, section.name
                start = index + 1


def _disasm_context(mem, address: int, *, before: int = 0x10, size: int = 0x40) -> list[str]:
    base = max(address - before, 0)
    blob = mem.read_bytes(base, size) or b""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    lines: list[str] = []
    for insn in md.disasm(blob, base):
        marker = "*" if address - 8 <= insn.address <= address + 8 else " "
        lines.append(f"{marker} 0x{insn.address:X}: {insn.mnemonic:<8} {insn.op_str}")
    return lines


def main() -> int:
    mem, status = attach_to_game()
    print(f"attach_status={status}")
    if mem is None:
        return 1

    try:
        hits_by_target: dict[int, list[tuple[int, str]]] = {value: [] for value in FIELD_TARGETS}
        for section in _iter_executable_sections(mem):
            print(
                f"scan_section {section.name} base=0x{section.address:X} "
                f"size=0x{section.size:X} chars=0x{section.characteristics:X}"
            )
            for target_value, address, section_name in _scan_field_hits(mem, section):
                hits_by_target[target_value].append((address, section_name))

        print()
        for target_value, target_name in FIELD_TARGETS.items():
            hits = hits_by_target.get(target_value, [])
            print(f"## field {target_name} 0x{target_value:X} hits={len(hits)}")
            for address, section_name in hits[:8]:
                print(f"  hit=0x{address:X} [{section_name}]")
                for line in _disasm_context(mem, address):
                    print(f"    {line}")
            print()
    finally:
        mem.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
