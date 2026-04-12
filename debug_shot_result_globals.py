"""Inspect the live globals used by the shot-result copy pipeline."""

from __future__ import annotations

from nba2k26_trainer.core.process import attach_to_game


CALL_SITES = (
    0x140F71B5B,
    0x140F7410D,
)

CALL_SITE_GLOBAL_SLOTS = {
    0x140F71B5B: 0x147D02F90,
    0x140F7410D: 0x147D02F90,
}


def _read_qword(mem, address: int) -> int:
    return int(mem.read_uint64(address) or 0)


def _read_u32(mem, address: int) -> int:
    return int(mem.read_uint32(address) or 0)


def _format_bytes(blob: bytes, limit: int = 32) -> str:
    if not blob:
        return "n/a"
    return blob[:limit].hex()


def main() -> int:
    mem, status = attach_to_game()
    print(f"attach_status={status}")
    if mem is None:
        return 1

    try:
        for call_site in CALL_SITES:
            slot = CALL_SITE_GLOBAL_SLOTS[call_site]
            manager = _read_qword(mem, slot)
            print()
            print(f"call_site=0x{call_site:X}")
            print(f"  global_slot=0x{slot:X}")
            print(f"  manager=0x{manager:X}")
            if manager <= 0:
                continue

            print(f"  [manager+0x18]   = 0x{_read_qword(mem, manager + 0x18):X}")
            print(f"  [manager+0x20]   = 0x{_read_qword(mem, manager + 0x20):X}")
            print(f"  [manager+0xEA0]  = 0x{_read_qword(mem, manager + 0xEA0):X}")
            print(f"  [manager+0x6A08] = 0x{_read_qword(mem, manager + 0x6A08):X}")
            print(f"  [manager+0x8968] = 0x{_read_qword(mem, manager + 0x8968):X}")
            print(f"  [manager+0x2EF8] = 0x{_read_u32(mem, manager + 0x2EF8):X}")
            print(f"  [manager+0x3260] = 0x{_read_u32(mem, manager + 0x3260):X}")
            print(f"  [manager+0x3264] = 0x{_read_u32(mem, manager + 0x3264):X}")
            print(f"  [manager+0x3268] = 0x{_read_u32(mem, manager + 0x3268):X}")

            for base_offset in (0x2F00, 0x3020, 0x3140):
                blob = mem.read_bytes(manager + base_offset, 0x40) or b""
                print(f"  block+0x{base_offset:X} head={_format_bytes(blob)}")
    finally:
        mem.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
