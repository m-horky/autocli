import enum
import logging


log = logging.getLogger(__file__)


class ParseError(Exception):
    pass


class ValidationError(Exception):
    pass


class _Section(enum.IntFlag):
    PATH = enum.auto()
    ARGS = enum.auto()
    METHOD = enum.auto()
    HEADER_KEY = enum.auto()
    HEADER_VALUE = enum.auto()
    QUERY_KEY = enum.auto()
    QUERY_VALUE = enum.auto()
    DATA = enum.auto()


class Parsed:
    path: str
    path_variables: dict[str, str]
    method: str
    headers: dict[str, str]
    queries: dict[str, str]
    data: str

    def __init__(self):
        self.path = ""
        self.path_variables = {}
        self.method = ""
        self.headers = {}
        self.queries = {}
        self.data = ""

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"path={self.path}, "
            f"path_variables={self.path_variables}, "
            f"method={self.method}, "
            f"headers={self.headers}, "
            f"queries={self.queries}, "
            f"data={self.data}"
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
                section = _Section.ARGS

            if section == _Section.ARGS:
                if arg == "-X":
                    section = _Section.METHOD
                    continue
                if arg == "-H":
                    section = _Section.HEADER_KEY
                    continue
                if arg == "-Q":
                    section = _Section.QUERY_KEY
                    continue
                if arg == "-D":
                    section = _Section.DATA
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
                section = _Section.ARGS
                continue

            if section == _Section.HEADER_KEY:
                key = arg
                result.headers[key] = ""
                section = _Section.HEADER_VALUE
                continue
            if section == _Section.HEADER_VALUE:
                result.headers[key] = arg
                section = _Section.ARGS
                continue

            if section == _Section.QUERY_KEY:
                key = arg
                result.queries[key] = ""
                section = _Section.QUERY_VALUE
                continue
            if section == _Section.QUERY_VALUE:
                result.queries[key] = arg
                section = _Section.ARGS
                continue

            if section == _Section.DATA:
                result.data = arg
                section = _Section.ARGS
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

        # Verify no invalid header has been passed in
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
        # Verify no invalid query has been passed in
        for k, _ in parsed.queries.items():
            try:
                [
                    p
                    for p in method["parameters"]
                    if p["name"] == k and p["in"] == "query"
                ][0]
            except IndexError:
                raise ValidationError(
                    f"Method {parsed.method} of path {parsed.path} does not take query parameter {k}."
                )

        # Verify all required parameters have been set
        for parameter in method["parameters"]:
            if parameter["required"] and (
                (
                    parameter["in"] == "header"
                    and parameter["name"] not in parsed.headers.keys()
                ) or (
                    parameter["in"] == "query"
                    and parameter["name"] not in parsed.queries.keys()
                )
            ):
                raise ValidationError(
                    f"Required {parameter['in']} parameter {parameter['name']} is missing."
                )
            
            if parameter["required"] and parameter["in"] == "body" and parsed.data == "":
                raise ValidationError("No body data have been set.")
        
        # TODO Verify the body structure

    def complete(self, *args: tuple[str]) -> tuple[str]:
        partial = Parsed()

        arg: str = ""
        key: str = ""
        section: _Section = _Section.PATH
        for arg in args:
            if section == _Section.PATH and arg.startswith("-"):
                section = _Section.ARGS

            if section == _Section.ARGS:
                if arg == "-X":
                    section = _Section.METHOD
                    continue
                if arg == "-H":
                    section = _Section.HEADER_KEY
                    continue
                if arg == "-Q":
                    section = _Section.QUERY_KEY
                    continue
                if arg == "-D":
                    section = _Section.DATA
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
                partial.method = arg.lower()
                section = _Section.ARGS
                continue

            if section == _Section.HEADER_KEY:
                key = arg
                partial.headers[key] = ""
                section = _Section.HEADER_VALUE
                continue
            if section == _Section.HEADER_VALUE:
                partial.headers[key] = arg
                section = _Section.ARGS
                continue

            if section == _Section.QUERY_KEY:
                key = arg
                partial.queries[key] = ""
                section = _Section.QUERY_VALUE
                continue
            if section == _Section.QUERY_VALUE:
                partial.queries[key] = arg
                section = _Section.ARGS
                continue

            if section == _Section.DATA:
                partial.data = arg
                section = _Section.ARGS
                continue

            break

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

            raise RuntimeError(f"Unhandled path completion case: {section=} {partial=} {arg=}")

        # If the method is incomplete, push the state back
        if section == _Section.ARGS:
            methods = list(sorted(self.specification["paths"][partial.path].keys()))
            if partial.method not in methods:
                section = _Section.METHOD
        # If the header key is incomplete, push the state back
        if section == _Section.HEADER_VALUE:
            methods = self.specification["paths"][partial.path]
            if partial.method in methods.keys():
                parameters = [p for p in methods[partial.method]["parameters"] if p["in"] == "header" and p["name"] not in partial.headers.keys()]
                if arg in partial.headers.keys() and arg not in parameters:
                    section = _Section.HEADER_KEY
        # If the query key is incomplete, push the state back
        if section == _Section.QUERY_VALUE:
            methods = self.specification["paths"][partial.path]
            if partial.method in methods.keys():
                parameters = [p for p in methods[partial.method]["parameters"] if p["in"] == "query" and p["name"] not in partial.queries.keys()]
                if arg in partial.headers.keys() and arg not in parameters:
                    section = _Section.QUERY_KEY

        if section == _Section.ARGS:
            methods = list(sorted(self.specification["paths"][partial.path].keys()))

            # Until we know the method, we cannot decide which arguments are possible
            if partial.method == "":
                # If there is only one possible method, complete it fully
                if len(methods) == 1:
                    return (f"-X {methods[0].upper()}")
                # Otherwise, only suggest a method argument
                return ("-X",)

            # We know the method, we can detect which types of arguments are possible
            result = set()
            for parameter in self.specification["paths"][partial.path][partial.method]["parameters"]:
                if parameter["in"] == "header" and parameter["name"] not in partial.headers.keys():
                    incomplete_headers = True
                    result.add("-H")
                    continue
                if parameter["in"] == "path" and parameter["name"] not in partial.queries.keys():
                    result.add("-Q")
                    continue
                # TODO payload

            return tuple(sorted(result))

        if section == _Section.METHOD:
            methods = self.specification["paths"][partial.path].keys()
            if partial.method:
                methods = [m for m in methods if m.startswith(partial.method)]
            return tuple(sorted(methods))

        if section == _Section.HEADER_KEY:
            # We cannot complete headers if we don't know the method
            if not partial.method:
                return tuple()

            # We don't complete headers which are not recongized
            for header in partial.headers.keys():
                if header not in [p for p in self.specification["paths"][partial.path][partial.method]["parameters"] if p["in"] == "header"]:
                    return tuple()

            missing = set()
            for parameter in self.specification["paths"][partial.path][partial.method]["parameters"]:
                if parameter["in"] == "header" and parameter["name"] not in partial.queries.keys():
                    missing.add(parameter["name"])
            return tuple(sorted(missing))

        if section == _Section.HEADER_VALUE:
            # Completion is not available for values
            return tuple()

        if section == _Section.QUERY_KEY:
            # We cannot complete headers if we don't know the method
            if not partial.method:
                return tuple()
            
            # We don't complete queries which are not recongized
            for header in partial.headers.keys():
                if header not in [p for p in self.specification["paths"][partial.path][partial.method]["parameters"] if p["in"] == "query"]:
                    return tuple()

            missing = set()
            for parameter in self.specification["paths"][partial.path][partial.method]["parameters"]:
                if parameter["in"] == "query" and parameter["name"] not in partial.queries.keys():
                    missing.add(parameter["name"])
            return tuple(sorted(missing))

        if section == _Section.QUERY_VALUE:
            # Completion is not available for values
            return tuple()

        if section == _Section.DATA:
            # TODO Completion for complex data types?
            # We could dump the whole thing and let the user fill in the blanks
            return tuple()

        raise RuntimeError(f"Unhandled completion case: {section=} {partial=} {arg=}")
