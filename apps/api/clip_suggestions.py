"""Explainable speech-window baseline; no claim of semantic or viral quality."""

from dataclasses import dataclass

from .captions import Word

ANALYSIS_VERSION = "speech-windows-v1"


@dataclass(frozen=True)
class Sentence:
    first: int
    last: int  # exclusive
    start_ms: int
    end_ms: int
    boundary_verified: bool


@dataclass(frozen=True)
class Suggestion:
    start_ms: int
    end_ms: int
    context_start_ms: int
    context_end_ms: int
    word_start_index: int
    word_end_index: int
    score: float
    reason_codes: list[str]


def sentences(words: list[Word], max_span_ms: int = 16_000) -> list[Sentence]:
    spans: list[Sentence] = []
    start = 0
    for index, word in enumerate(words):
        next_word = words[index + 1] if index + 1 < len(words) else None
        punctuated = word.text.rstrip().endswith((".", "?", "!", "…"))
        paused = bool(next_word and next_word.start_ms - word.end_ms >= 650)
        forced = word.end_ms - words[start].start_ms >= max_span_ms
        if punctuated or paused or forced or next_word is None:
            spans.append(Sentence(
                first=start, last=index + 1,
                start_ms=words[start].start_ms, end_ms=word.end_ms,
                boundary_verified=punctuated or paused,
            ))
            start = index + 1
    return spans


def overlap_ratio(left: Suggestion, right: Suggestion) -> float:
    common = max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))
    union = max(left.end_ms, right.end_ms) - min(left.start_ms, right.start_ms)
    return common / union if union else 0


def suggest_clips(
    words: list[Word], source_duration_ms: int, *, min_ms: int = 12_000,
    target_ms: int = 32_000, max_ms: int = 60_000,
    context_ms: int = 5_000, max_results: int = 12,
) -> list[Suggestion]:
    if not 0 < min_ms <= target_ms <= max_ms <= source_duration_ms:
        raise ValueError("Invalid clip duration settings or source too short")
    if context_ms < 0 or max_results < 1:
        raise ValueError("Invalid context or result limit")
    if any(word.end_ms > source_duration_ms for word in words):
        raise ValueError("Transcript word exceeds source duration")
    if any(right.start_ms < left.start_ms
           for left, right in zip(words, words[1:], strict=False)):
        raise ValueError("Transcript words are not chronological")
    spans = sentences(words)
    proposed: list[Suggestion] = []
    for start_index, start in enumerate(spans):
        eligible = [end for end in spans[start_index:]
                    if min_ms <= end.end_ms - start.start_ms <= max_ms]
        if not eligible:
            continue
        end = min(eligible, key=lambda item: abs(item.end_ms - start.start_ms - target_ms))
        relevant = words[start.first:end.last]
        duration = end.end_ms - start.start_ms
        speech_ms = sum(word.end_ms - word.start_ms for word in relevant)
        coverage = min(1.0, speech_ms / duration)
        question = any(word.text.rstrip().endswith("?") for word in relevant)
        speaker_turn = any(
            left.speaker_id is not None and right.speaker_id is not None
            and left.speaker_id != right.speaker_id
            for left, right in zip(relevant, relevant[1:], strict=False)
        )
        reasons = ["HIGH_SPEECH_COVERAGE" if coverage >= 0.6
                   else "LOW_SPEECH_COVERAGE"]
        if question:
            reasons.append("QUESTION")
        if speaker_turn:
            reasons.append("SPEAKER_TURN")
        if not end.boundary_verified:
            reasons.append("BOUNDARY_NEEDS_REVIEW")
        if start_index and not spans[start_index - 1].boundary_verified:
            reasons.append("START_NEEDS_REVIEW")
        score = min(1.0, 0.15 + 0.5 * coverage + 0.1 * question
                    + 0.1 * speaker_turn + 0.05 * end.boundary_verified)
        proposed.append(Suggestion(
            start_ms=start.start_ms, end_ms=end.end_ms,
            context_start_ms=max(0, start.start_ms - context_ms),
            context_end_ms=min(source_duration_ms, end.end_ms + context_ms),
            word_start_index=start.first, word_end_index=end.last,
            score=round(score, 3), reason_codes=reasons,
        ))
    accepted: list[Suggestion] = []
    for candidate in sorted(proposed, key=lambda item: (-item.score, item.start_ms)):
        if all(overlap_ratio(candidate, item) < 0.7 for item in accepted):
            accepted.append(candidate)
        if len(accepted) >= max_results:
            break
    return sorted(accepted, key=lambda item: item.start_ms)
