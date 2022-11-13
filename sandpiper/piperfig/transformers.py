__all__ = [
    "do_transformations",
    "do_transformations_back",
    "ConfigTransformer",
    "FromType",
    "Bounded",
    "MaybeRelativePath",
]

from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, Optional, Type, TypeVar, overload

from .misc import typecheck

V1 = TypeVar("V1")
V2 = TypeVar("V2")


def do_transformations(value, annotation):
    if not hasattr(annotation, "__origin__") or not hasattr(annotation, "__metadata__"):
        raise TypeError(f"Value {annotation} is not an Annotated instance")

    target_type: type = annotation.__origin__
    metadata: tuple = annotation.__metadata__
    used_implicit_fromtype = False
    for trans in metadata:
        if not isinstance(trans, ConfigTransformer):
            # Other annotations are okay but we'll ignore them
            continue

        if used_implicit_fromtype:
            # We found a FromType with an implicit output type already, but
            # encountered another transformer. Functionally, this is possible,
            # but for readability's sake I am not allowing this.
            raise ValueError(
                "A FromType transformer with an implicit to_type may only be "
                "the last transformer in the sequence."
            )

        if isinstance(trans, FromType) and trans.to_type is None:
            # to_type will be implicitly set to the origin type
            used_implicit_fromtype = True
            trans.to_type = target_type
            value = trans.transform(value)
            # If we have another transformer after this and raise an error for
            # that, we don't want to forget that this transformer is implicit
            # in any future parses.
            trans.to_type = None
        else:
            value = trans.transform(value)

    return value


def do_transformations_back(value, annotation):
    if not hasattr(annotation, "__origin__") or not hasattr(annotation, "__metadata__"):
        raise TypeError(f"Value {annotation} is not an Annotated instance")

    target_type: type = annotation.__origin__
    metadata: tuple = annotation.__metadata__
    found_transformer = False
    for trans in metadata[::-1]:
        if not isinstance(trans, ConfigTransformer):
            # Other annotations are okay but we'll ignore them
            continue

        if isinstance(trans, FromType) and trans.to_type is None:
            if found_transformer:
                raise ValueError(
                    "A FromType transformer with an implicit to_type may only be "
                    "the last transformer in the sequence."
                )

            # to_type will be implicitly set to the origin type
            trans.to_type = target_type
            value = trans.transform_back(value)
            # We don't want to forget that this transformer is implicit
            # in any future parses.
            trans.to_type = None
        else:
            value = trans.transform_back(value)

        if not found_transformer:
            found_transformer = True

    return value


class ConfigTransformer(metaclass=ABCMeta):
    @property
    @abstractmethod
    def in_type(self) -> Type[V1]:
        pass

    @property
    @abstractmethod
    def out_type(self) -> Type[V2]:
        pass

    @abstractmethod
    def transform(self, value: V1) -> V2:
        pass

    @abstractmethod
    def transform_back(self, value: V2) -> V1:
        pass


class FromType(ConfigTransformer):

    __implicit_err_msg = (
        "to_type is None. This may be done to implicitly set it to the final "
        "annotated type, however this is only handled in do_transformations. "
        "Use that function to evaluate implicit to_type."
    )

    # TODO update to generic type[] once jetbrains fixes a bug in pycharm
    def __init__(self, from_type: Type[V1], to_type: Optional[Type[V2]] = None):
        self.from_type = from_type
        self.to_type = to_type

    def __repr__(self):
        return f"FromType({self.from_type.__name__!r}, {self.to_type.__name__!r})"

    def __str__(self):
        return f"<FromType from={self.from_type} to={self.to_type}>"

    @property
    def in_type(self) -> type:
        return self.from_type

    @property
    def out_type(self) -> type:
        return self.to_type

    def transform(self, value: V1) -> V2:
        typecheck(self.from_type, value, "value")
        if self.to_type is not None:
            return self.to_type(value)
        raise RuntimeError(self.__implicit_err_msg)

    def transform_back(self, value: V2) -> V1:
        if self.to_type is not None:
            typecheck(self.to_type, value, "value")
        else:
            raise RuntimeError(self.__implicit_err_msg)
        return self.from_type(value)


# noinspection PyShadowingBuiltins
class Bounded(ConfigTransformer):
    @overload
    def __init__(self, min: V1, max: V1):
        pass

    @overload
    def __init__(self, min: None, max: V1):
        pass

    @overload
    def __init__(self, min: V1, max: None):
        pass

    def __init__(self, min: Any, max: Any):
        if min is not None and max is not None:
            if type(min) != type(max):
                raise TypeError(
                    f"min and max must be the same type, got {type(min)} and "
                    f"{type(max)}"
                )
            if min > max:
                raise ValueError(f"min {min} is greater than max {max}")
            self.type = type(min)
        elif min is not None:
            self.type = type(min)
        else:
            self.type = type(max)

        self.min = min
        self.max = max

    def __repr__(self):
        return f"Bounded({self.min}, {self.max})"

    def __str__(self):
        return f"<Bounded type={self.type} min={self.min} max={self.max}>"

    @property
    def in_type(self) -> type:
        return self.type

    @property
    def out_type(self) -> type:
        return self.type

    def check(self, value: V1):
        if self.min is not None and value < self.min:
            raise ValueError(
                f"Value {value} must be greater than or equal to {self.min}"
            )
        if self.max is not None and value > self.max:
            raise ValueError(f"Value {value} must be less than or equal to {self.max}")

    def transform(self, value: V1) -> V1:
        typecheck(self.type, value, "value")
        self.check(value)
        return value

    def transform_back(self, value: V1) -> V1:
        return self.transform(value)


class MaybeRelativePath(ConfigTransformer):
    def __init__(self, root_path: Path):
        if not isinstance(root_path, Path):
            raise TypeError(f"root_path must be of type Path, got {type(root_path)}")
        self.root_path = root_path

    def __repr__(self):
        return f"MaybeRelativePath({self.root_path!r})"

    def __str__(self):
        return f"<MaybeRelativePath root_path={self.root_path}>"

    @property
    def in_type(self) -> type:
        return str

    @property
    def out_type(self) -> type:
        return Path

    def transform(self, value: str) -> Path:
        typecheck(str, value, "value")
        path = Path(value)
        if not path.is_absolute():
            return self.root_path / path
        return path

    def transform_back(self, value: Path) -> str:
        typecheck(Path, value, "value", use_isinstance=True)
        if value.is_relative_to(self.root_path):
            return str(value.relative_to(self.root_path))
        return str(value.absolute())
