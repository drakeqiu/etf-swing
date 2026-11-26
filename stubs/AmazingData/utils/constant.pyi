import builtins
import enum

# stubgen 将该 SDK 枚举的 value 错误推断为 Period；运行时值为 int。
class Period(enum.Enum):
    day: Period

    @builtins.property
    def value(self) -> builtins.int: ...
