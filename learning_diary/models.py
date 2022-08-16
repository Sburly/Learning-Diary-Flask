from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Entry:
    _id: str
    date: str
    title: str
    description: str
    tag: list[str] = field(default_factory=list)


@dataclass
class User:
    _id: str
    email: str
    password: str
    entries: list[str] = field(default_factory=list)
