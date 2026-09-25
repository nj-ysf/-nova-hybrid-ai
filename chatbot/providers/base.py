from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass


class ProviderError(Exception):
    def __init__(self):
        super().__init__("Model service unavailable.")


@dataclass(frozen=True)
class Turn:
    role: str
    content: str


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: Sequence[Turn], *, max_tokens: int) -> Generation: ...

    @abstractmethod
    def stream(self, messages: Sequence[Turn], *, max_tokens: int) -> Iterator[str]: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    def estimate_tokens(self, messages: Sequence[Turn]) -> int:
        # Conservative byte-based budget for unknown tokenizers, including role framing.
        return sum(len(turn.content.encode("utf-8")) + 32 for turn in messages) + 32
