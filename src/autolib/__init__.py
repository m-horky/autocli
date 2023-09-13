import enum
import logging


log = logging.getLogger(__file__)


class ParseError(Exception):
    pass


class ValidationError(Exception):
    pass


class _Section(enum.IntFlag):
    ANY = enum.auto()
    PATH = enum.auto()
    METHOD = enum.auto()
    HEADER_KEY = enum.auto()
    HEADER_VALUE = enum.auto()
    QUERY_KEY = enum.auto()
    QUERY_VALUE = enum.auto()
    PAYLOAD = enum.auto()


class _Completion(enum.IntEnum):
    COMPLETE = enum.auto()
    """Completion is already done."""
    CONTINUATION = enum.auto()
    """The word can continue as..."""
    OPTIONS = enum.auto()
    """Next words may be..."""
    ERROR = enum.auto()
    """No completion is possible."""
    UNKNOWN = enum.auto()
    """No value has been detected yet."""


class Parsed:
    path: str
    path_variables: dict[str, str]
    method: str
    headers: dict[str, str]
    queries: dict[str, str]

    def __init__(self):
        self.path = ""
        self.path_variables = {}
        self.method = ""
        self.headers = {}
        self.queries = {}

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"path={self.path}, "
            f"path_variables={self.path_variables}, "
            f"method={self.method}, "
            f"headers={self.headers}, "
            f"queries={self.queries}"
            ")"
        )


class AutoTool:
    def __init__(self, specification: dict):
        self.specification = specification

    def parse(self, *args: tuple[str]) -> Parsed:
        result = Parsed()

        key: str = ""
        section = _Section.PATH
        for arg in args:
            if section == _Section.PATH and arg.startswith("-"):
                section = _Section.ANY

            if section == _Section.ANY:
                if arg == "-X":
                    section = _Section.METHOD
                    continue
                if arg == "-H":
                    section = _Section.HEADER_KEY
                    continue
                if arg == "-Q":
                    section = _Section.QUERY_KEY
                    continue
                raise ParseError(f"Unexpected {arg}.")

            if section == _Section.PATH:
                if "=" not in arg:
                    result.path += f"/{arg}"
                else:
                    key, value = arg.split("=", 1)
                    result.path += f"/{{{key}}}"
                    result.path_variables[key] = value
                continue

            if section == _Section.METHOD:
                if result.method:
                    raise ParseError("Method can only be specified once.")
                result.method = arg.lower()
                section = _Section.ANY
                continue

            if section == _Section.HEADER_KEY:
                key = arg
                section = _Section.HEADER_VALUE
                continue
            if section == _Section.HEADER_VALUE:
                result.headers[key] = arg
                section = _Section.ANY
                continue

            if section == _Section.QUERY_KEY:
                key = arg
                section = _Section.QUERY_VALUE
                continue
            if section == _Section.QUERY_VALUE:
                result.queries[key] = arg
                section = _Section.ANY
                continue

            raise ParseError(f"Unexpected {arg}.")

        return result

    def verify(self, parsed: Parsed) -> None:
        if parsed.path not in self.specification["paths"].keys():
            raise ValidationError(f"Path {parsed.path} is not valid path.")

        path: dict = self.specification["paths"][parsed.path]
        if parsed.method not in path.keys():
            raise ValidationError(
                f"Path {parsed.path} does not define method {parsed.method}."
            )

        method: dict = path[parsed.method]

        for k, _ in parsed.headers.items():
            try:
                [
                    p
                    for p in method["parameters"]
                    if p["name"] == k and p["in"] == "header"
                ][0]
            except IndexError:
                raise ValidationError(
                    f"Method {parsed.method} of path {parsed.path} does not take header {k}."
                )
        for k, _ in parsed.queries.items():
            try:
                [
                    p
                    for p in method["parameters"]
                    if p["name"] == k and p["in"] == "path"
                ][0]
            except IndexError:
                raise ValidationError(
                    f"Method {parsed.method} of path {parsed.path} does not take query parameter {k}."
                )

        for parameter in method["parameters"]:
            if parameter["required"] and (
                (
                    parameter["in"] == "header"
                    and parameter["name"] not in parsed.headers.keys()
                )
                or (
                    parameter["in"] == "query"
                    and parameter["name"] not in parsed.queries.keys()
                )
            ):
                raise ValidationError(
                    f"Required {parameter['in']} parameter {parameter['name']} is missing."
                )

    def complete(self, *args: tuple[str]) -> tuple[str]:
        partial = Parsed()

        arg: str = ""
        key: str = ""
        section: _Section = _Section.PATH
        for arg in args:
            if section == _Section.PATH and arg.startswith("-"):
                section = _Section.ANY

            if section == _Section.ANY:
                if arg == "-X":
                    section = _Section.METHOD
                    continue
                if arg == "-H":
                    section = _Section.HEADER_KEY
                    continue
                if arg == "-Q":
                    section = _Section.QUERY_KEY
                    continue
                break

            if section == _Section.PATH:
                if "=" not in arg:
                    partial.path += f"/{arg}"
                else:
                    key, value = arg.split("=", 1)
                    partial.path += f"/{{{key}}}"
                    partial.path_variables[key] = value
                continue

            if section == _Section.METHOD:
                method = arg
                section = _Section.ANY
                continue

            if section == _Section.HEADER_KEY:
                key = arg
                section = _Section.HEADER_VALUE
                continue
            if section == _Section.HEADER_VALUE:
                partial.headers[key] = arg
                section = _Section.ANY
                continue

            if section == _Section.QUERY_KEY:
                key = arg
                section = _Section.QUERY_VALUE
                continue
            if section == _Section.QUERY_VALUE:
                partial.queries[key] = arg
                section = _Section.ANY
                continue

            break

        print(f"{arg=}")
        print(f"{partial=}")
        print(f"{section=}")

        if section == _Section.PATH:
            current_path: str = "/" + "/".join(args)

            # Find all paths matching the written one
            path_continuations = [
                path
                for path
                in self.specification["paths"].keys()
                if path.startswith(partial.path)
            ]
            # Remove common prefix that has already been written
            cut_path_continuations = [
                path.removeprefix(current_path)
                for path
                in path_continuations
            ]

            # Find out if we can continue with the same word or with more words
            same_words = []
            next_words = []
            for continuation in cut_path_continuations:
                if continuation.startswith("/"):
                    next_words.append(continuation.removeprefix("/"))
                else:
                    same_words.append(continuation)

            # We can continue in a word
            if same_words:
                return tuple(sorted(set([arg + word.split("/", 1)[0] for word in same_words])))
            
            # There are more words that can be completed
            if next_words:
                result = set()
                for word in next_words:
                    word = word.split("/", 1)[0]
                    if word.startswith("{") and word.endswith("}"):
                        word = word[1:-1] + "="
                    result.add(word)
                return tuple(sorted(result))

            raise RuntimeError(f"Unhandled completion case: {section=} {partial=} {arg=}")
