import re
from dataclasses import dataclass

WHITESPACE = re.compile(r"\s+")


@dataclass
class SourceMatch:
    line_start: int
    line_end: int
    page: str | None
    quote: str

    @property
    def anchor(self) -> str:
        if self.line_start == self.line_end:
            return f"L{self.line_start}"
        return f"L{self.line_start}-L{self.line_end}"


class DocumentIndex:
    def __init__(self, text: str, *, page_markers: bool = False):
        self.lines = text.splitlines()
        self.page_by_line = self._build_page_map() if page_markers else {}

    def _normalize(self, text: str) -> str:
        return WHITESPACE.sub(" ", text).strip().lower()

    def _build_page_map(self) -> dict[int, str]:
        page_map: dict[int, str] = {}
        current_page: str | None = None

        for line_number, line in enumerate(self.lines, start=1):
            total_pages = re.search(r"Total Pages:\s*(\d+)", line, re.IGNORECASE)
            if total_pages:
                current_page = f"cover ({total_pages.group(1)} pages total)"
                page_map[line_number] = current_page
                continue

            page_match = re.match(r"^\s*(\d{1,2})\s*$", line)
            if page_match and line_number > 1:
                previous = self.lines[line_number - 2].lower()
                if "callstreet" in previous or "factset" in previous or "corrected transcript" in previous:
                    current_page = page_match.group(1)
            if current_page:
                page_map[line_number] = current_page

        return page_map

    def page_for_line(self, line_number: int) -> str | None:
        if line_number in self.page_by_line:
            return self.page_by_line[line_number]
        for candidate in range(line_number, 0, -1):
            if candidate in self.page_by_line:
                return self.page_by_line[candidate]
        return None

    def _normalized_full_text(self) -> str:
        return self._normalize("\n".join(self.lines))

    def _line_range_for_span(self, start: int, end: int) -> tuple[int, int, str]:
        cursor = 0
        line_start = 1
        line_end = 1
        selected_lines: list[str] = []

        for line_number, line in enumerate(self.lines, start=1):
            normalized_line = self._normalize(line)
            if not normalized_line:
                continue
            line_start_idx = cursor
            line_end_idx = cursor + len(normalized_line)
            if line_end_idx > start and line_start_idx < end:
                if not selected_lines:
                    line_start = line_number
                selected_lines.append(line.strip())
                line_end = line_number
            cursor = line_end_idx + 1

        quote = self._normalize(" ".join(selected_lines))
        return line_start, line_end, quote[:500]

    def _match_span(self, start: int, end: int) -> SourceMatch:
        line_start, line_end, quote = self._line_range_for_span(start, end)
        return SourceMatch(
            line_start=line_start,
            line_end=line_end,
            page=self.page_for_line(line_start),
            quote=quote,
        )

    def find_quote(self, quote: str, *, min_ratio: float = 0.72) -> SourceMatch | None:
        normalized_quote = self._normalize(quote)
        if len(normalized_quote) < 20:
            return None

        haystack = self._normalized_full_text()
        start = haystack.find(normalized_quote)
        if start != -1:
            return self._match_span(start, start + len(normalized_quote))

        quote_words = normalized_quote.split()
        for size in (14, 12, 10, 8, 6):
            if len(quote_words) >= size:
                seed = " ".join(quote_words[:size])
                seed_start = haystack.find(seed)
                if seed_start != -1:
                    return self._match_span(seed_start, seed_start + len(seed))

        return self._best_fuzzy_match(normalized_quote, min_ratio=min_ratio)

    def _locate_exact(self, normalized_quote: str) -> SourceMatch | None:
        haystack = self._normalized_full_text()
        start = haystack.find(normalized_quote)
        if start == -1:
            return None
        return self._match_span(start, start + len(normalized_quote))

    def _best_fuzzy_match(self, normalized_quote: str, *, min_ratio: float) -> SourceMatch | None:
        quote_words = normalized_quote.split()
        if len(quote_words) < 4:
            return None

        best: SourceMatch | None = None
        best_score = 0.0
        window = min(max(len(quote_words) + 4, 8), 20)

        for start in range(len(self.lines)):
            end = min(start + window, len(self.lines))
            chunk = self._normalize(" ".join(self.lines[start:end]))
            score = self._overlap_score(normalized_quote, chunk)
            if score > best_score:
                best_score = score
                quote = " ".join(line.strip() for line in self.lines[start:end] if line.strip())
                best = SourceMatch(
                    line_start=start + 1,
                    line_end=end,
                    page=self.page_for_line(start + 1),
                    quote=quote[:500],
                )

        if best and best_score >= min_ratio:
            return best
        return None

    @staticmethod
    def _overlap_score(left: str, right: str) -> float:
        left_words = set(left.split())
        right_words = set(right.split())
        if not left_words or not right_words:
            return 0.0
        return len(left_words & right_words) / len(left_words)

    def contains_phrases(self, phrases: list[str]) -> bool:
        haystack = self._normalize("\n".join(self.lines))
        return any(self._normalize(phrase) in haystack for phrase in phrases if phrase)

    def extract_phrases(self, text: str, *, sizes: tuple[int, ...] = (4, 3)) -> list[str]:
        words = [word for word in re.findall(r"[A-Za-z0-9$%]+", text.lower()) if len(word) > 2]
        phrases: list[str] = []
        for size in sizes:
            for index in range(0, max(len(words) - size + 1, 0)):
                phrase = " ".join(words[index : index + size])
                if len(phrase) >= 12:
                    phrases.append(phrase)
        return phrases

    def extract_ceo_section(self) -> "DocumentIndex":
        blocks = re.split(r"\.{10,}", "\n".join(self.lines))
        ceo_lines: list[str] = []
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 3:
                continue
            if re.search(r"Chief Executive Officer|CEO &|CEO,", lines[1], re.IGNORECASE):
                ceo_lines.extend(lines[2:])
        return DocumentIndex("\n".join(ceo_lines), page_markers=False)
