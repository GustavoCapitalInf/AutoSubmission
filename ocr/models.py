from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2.0

@dataclass
class OCRWord:
    text: str
    bbox: BBox
    confidence: float = 1.0

@dataclass
class OCRLine:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    bbox: BBox | None = None
    y_center: float = 0.0

@dataclass
class Transaction:
    date: str | None
    description: str
    debit: float | None
    credit: float | None
    balance: float | None
    raw_line: str

@dataclass
class AccountInfo:
    bank: str
    account_holder: str | None = None
    account_number: str | None = None
    statement_period: str | None = None
    beginning_balance: float | None = None
    ending_balance: float | None = None

@dataclass
class StatementResult:
    account_info: AccountInfo
    transactions: list[Transaction] = field(default_factory=list)
    raw_text: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
