"""Spatial helpers for rectangular grave markers on the uploaded plan."""

from collections import defaultdict


MARKER_WIDTH = 58
MARKER_HEIGHT = 50


class PositionIndex:
    """Quickly find intersecting marker rectangles in a large import batch."""

    def __init__(self, positions=()):
        self._cells = defaultdict(list)
        for x, y in positions:
            self.add(x, y)

    def _cell(self, x, y):
        return x // MARKER_WIDTH, y // MARKER_HEIGHT

    def overlaps(self, x, y):
        return self.overlap(x, y) is not None

    def overlap(self, x, y):
        cell_x, cell_y = self._cell(x, y)
        for bucket_x in range(cell_x - 1, cell_x + 2):
            for bucket_y in range(cell_y - 1, cell_y + 2):
                for other_x, other_y in self._cells.get((bucket_x, bucket_y), ()):
                    if (
                        x < other_x + MARKER_WIDTH
                        and x + MARKER_WIDTH > other_x
                        and y < other_y + MARKER_HEIGHT
                        and y + MARKER_HEIGHT > other_y
                    ):
                        return other_x, other_y
        return None

    def add(self, x, y):
        self._cells[self._cell(x, y)].append((x, y))
