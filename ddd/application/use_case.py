"""Small command dispatch helper for application use cases."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

CommandT = TypeVar("CommandT")
ResultT = TypeVar("ResultT")


def handles(command_type: type[CommandT]) -> Callable[[Callable[..., ResultT]], Callable[..., ResultT]]:
    def decorator(method: Callable[..., ResultT]) -> Callable[..., ResultT]:
        setattr(method, "_command_type", command_type)
        return method

    return decorator


class UseCase:
    def handle(self, command: object) -> Any:
        for name in dir(self):
            method = getattr(self, name)
            handler = getattr(method, "__func__", method)
            command_type = getattr(handler, "_command_type", None)
            if command_type is not None and isinstance(command, command_type):
                return method(command)

        raise TypeError(f"Unsupported command: {type(command).__name__}")
