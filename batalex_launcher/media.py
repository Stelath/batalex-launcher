"""Media library: scans folders for photos/videos and cycles through them."""
from __future__ import annotations

import random
from pathlib import Path


class MediaLibrary:
    """An endless shuffled (or ordered) iterator over media files found in
    ``dirs`` (searched recursively)."""

    def __init__(
        self,
        dirs: list[Path],
        image_exts: list[str],
        video_exts: list[str],
        shuffle: bool = True,
    ) -> None:
        self._dirs = [Path(d) for d in dirs]
        self.image_exts = {e.lower() for e in image_exts}
        self.video_exts = {e.lower() for e in video_exts}
        self._all_exts = self.image_exts | self.video_exts
        self.shuffle = shuffle
        self._items: list[Path] = []
        self._index = 0
        self._last: Path | None = None
        self.scan()

    # ------------------------------------------------------------------ #
    def scan(self) -> None:
        items: list[Path] = []
        for d in self._dirs:
            if d.is_dir():
                try:
                    items.extend(
                        p
                        for p in sorted(d.rglob("*"))
                        if p.is_file() and p.suffix.lower() in self._all_exts
                    )
                except OSError:
                    continue
            elif d.is_file() and d.suffix.lower() in self._all_exts:
                items.append(d)
        if self.shuffle:
            random.shuffle(items)
            # Avoid replaying the same file first after a reshuffle.
            if len(items) > 1 and items and items[0] == self._last:
                items.append(items.pop(0))
        else:
            items.sort()
        self._items = items
        self._index = 0

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> list[Path]:
        return list(self._items)

    @property
    def dirs(self) -> list[Path]:
        return list(self._dirs)

    def next(self) -> Path | None:
        if self._index >= len(self._items):
            # Rescan: picks up newly added files and handles an empty library.
            self.scan()
        if not self._items:
            return None
        item = self._items[self._index]
        self._index += 1
        self._last = item
        return item

    def is_video(self, path: Path) -> bool:
        return path.suffix.lower() in self.video_exts
