import bisect
import os
import struct


_CACHE = {}


def measure_text(font_path, text, pixel_size):
    """Return a TrueType advance width in pixels, or None when unavailable."""
    if not font_path or not text:
        return 0.0 if not text else None
    resolved = _translate_path(font_path)
    try:
        metrics = _CACHE.get(resolved)
        if metrics is None:
            metrics = TrueTypeMetrics(resolved)
            _CACHE[resolved] = metrics
        return metrics.text_width(text, pixel_size)
    except (IndexError, KeyError, OSError, struct.error, ValueError):
        return None


def _translate_path(path):
    if not path.startswith("special://"):
        return path
    try:
        import xbmcvfs

        return xbmcvfs.translatePath(path)
    except (ImportError, AttributeError):
        return path


class TrueTypeMetrics:
    """Minimal dependency-free reader for TrueType horizontal advances."""

    def __init__(self, path):
        if not os.path.isfile(path):
            raise OSError("font not found")
        with open(path, "rb") as handle:
            self.data = handle.read()
        self.tables = self._table_directory()
        self.units_per_em = self._u16(self.tables["head"] + 18)
        glyph_count = self._u16(self.tables["maxp"] + 4)
        metric_count = self._u16(self.tables["hhea"] + 34)
        self.advances = self._horizontal_advances(glyph_count, metric_count)
        self.cmap = self._select_cmap()

    def text_width(self, text, pixel_size):
        fallback = self.units_per_em * 0.55
        total = 0
        for char in text:
            glyph = self.cmap.glyph_id(ord(char))
            total += self.advances[glyph] if 0 <= glyph < len(self.advances) else fallback
        return total * float(pixel_size) / self.units_per_em

    def _table_directory(self):
        count = self._u16(4)
        tables = {}
        for index in range(count):
            offset = 12 + index * 16
            tag = self.data[offset:offset + 4].decode("latin-1")
            tables[tag] = self._u32(offset + 8)
        return tables

    def _horizontal_advances(self, glyph_count, metric_count):
        base = self.tables["hmtx"]
        advances = [self._u16(base + index * 4) for index in range(metric_count)]
        if not advances:
            raise ValueError("font has no horizontal metrics")
        advances.extend([advances[-1]] * max(0, glyph_count - len(advances)))
        return advances

    def _select_cmap(self):
        base = self.tables["cmap"]
        count = self._u16(base + 2)
        candidates = []
        for index in range(count):
            record = base + 4 + index * 8
            platform = self._u16(record)
            encoding = self._u16(record + 2)
            subtable = base + self._u32(record + 4)
            fmt = self._u16(subtable)
            priority = _cmap_priority(platform, encoding, fmt)
            if priority is not None:
                candidates.append((priority, fmt, subtable))
        if not candidates:
            raise ValueError("font has no supported Unicode cmap")
        _, fmt, offset = min(candidates)
        return _Cmap12(self, offset) if fmt == 12 else _Cmap4(self, offset)

    def _u16(self, offset):
        return struct.unpack_from(">H", self.data, offset)[0]

    def _i16(self, offset):
        return struct.unpack_from(">h", self.data, offset)[0]

    def _u32(self, offset):
        return struct.unpack_from(">I", self.data, offset)[0]


def _cmap_priority(platform, encoding, fmt):
    if fmt == 12 and platform == 3 and encoding == 10:
        return 0
    if fmt == 12 and platform == 0:
        return 1
    if fmt == 4 and platform == 3 and encoding in (1, 10):
        return 2
    if fmt == 4 and platform == 0:
        return 3
    return None


class _Cmap4:
    def __init__(self, font, offset):
        self.font = font
        self.offset = offset
        self.segment_count = font._u16(offset + 6) // 2
        self.end_base = offset + 14
        self.ends = [font._u16(self.end_base + index * 2) for index in range(self.segment_count)]
        self.start_base = self.end_base + self.segment_count * 2 + 2
        self.delta_base = self.start_base + self.segment_count * 2
        self.range_base = self.delta_base + self.segment_count * 2

    def glyph_id(self, codepoint):
        if codepoint > 0xFFFF:
            return 0
        index = bisect.bisect_left(self.ends, codepoint)
        if index >= self.segment_count:
            return 0
        start = self.font._u16(self.start_base + index * 2)
        if codepoint < start:
            return 0
        delta = self.font._i16(self.delta_base + index * 2)
        range_offset_location = self.range_base + index * 2
        range_offset = self.font._u16(range_offset_location)
        if range_offset == 0:
            return (codepoint + delta) & 0xFFFF
        glyph_location = range_offset_location + range_offset + (codepoint - start) * 2
        glyph = self.font._u16(glyph_location)
        return (glyph + delta) & 0xFFFF if glyph else 0


class _Cmap12:
    def __init__(self, font, offset):
        self.font = font
        count = font._u32(offset + 12)
        group_base = offset + 16
        self.groups = []
        for index in range(count):
            group = group_base + index * 12
            self.groups.append((font._u32(group), font._u32(group + 4), font._u32(group + 8)))
        self.starts = [group[0] for group in self.groups]

    def glyph_id(self, codepoint):
        index = bisect.bisect_right(self.starts, codepoint) - 1
        if index < 0:
            return 0
        start, end, glyph = self.groups[index]
        return glyph + codepoint - start if codepoint <= end else 0
