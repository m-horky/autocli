import enum
import re
import logging
from typing import Optional


log = logging.getLogger(__file__)


class ParseError(Exception):
    pass


class ValidationError(Exception):
    pass


class _State(enum.IntFlag):
    NOT_SET = enum.auto()
    PATH = enum.auto()
    ARGS = enum.auto()
    FLAG = enum.auto()
    METHOD = enum.auto()
    HEADER_KEY = enum.auto()
    HEADER_VALUE = enum.auto()
    QUERY_KEY = enum.auto()
    QUERY_VALUE = enum.auto()
    DATA = enum.auto()


class Query:
    path: str
    path_variables: dict[str, str]
    method: str
    headers: dict[str, str]
    queries: dict[str, str]
    data: str

    _state: _State

    def __init__(
        self,
        *,
        path: Optional[str] = None,
        path_variables: Optional[dict[str, str]]= None,
        method: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        queries: Optional[dict[str, str]] = None,
        data: Optional[str] = None,
    ):
        self.path = path or ""
        self.path_variables = path_variables or {}
        self.method = method or ""
        self.headers = headers or {}
        self.queries = queries or {}
        self.data = data or ""
        self._state = _State.NOT_SET

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
    
    def __eq__(self, other) -> bool:
        if type(self) is not type(other):
            return False
        other: "Query"
        if self.path != other.path:
            return False
        if self.method != other.method:
            return False
        if self.path_variables != other.path_variables:
            return False
        if self.headers != other.headers:
            return False
        if self.queries != other.queries:
            return False
        if self.data != other.data:
            return False
        return True


class AutoTool:
    def __init__(self, specification: dict):
        self.specification = specification
    
    def _fix_args(self, args: list[str]) -> list[str]:
        """Fix the input.
        
        Bash `complete` (via `readline`) is splitting the input on `=`, making
        it unusable for the grammar written below.

        This function takes in the input from `sys.argv` and joins back items
        that were separated into `foo`, `=`, `bar` triplets.
        """
        fixed_args: list[str] = []
        join_next: bool = False
        for arg in args:
            if join_next:
                fixed_args[-1] = fixed_args[-1] + "=" + arg
                join_next = False
                continue
            if arg != "=":
                fixed_args.append(arg)
                continue
            join_next = True
        return fixed_args

    def parse(self, args: list[str]) -> Query:
        result = Query()

        key: str = ""
        state = _State.PATH
        for arg in self._fix_args(args):
            # Dash starts a split betwen path and arguments
            if state == _State.PATH and arg.startswith("-"):
                state = _State.ARGS

            # Descend into specific branch
            if state == _State.ARGS:
                if arg == "-X":
                    state = _State.METHOD
                    continue
                if arg == "-H":
                    state = _State.HEADER_KEY
                    continue
                if arg == "-Q":
                    state = _State.QUERY_KEY
                    continue
                if arg == "-D":
                    state = _State.DATA
                    continue
                
                # Partial argument, like '-'
                state = _State.FLAG
                continue

            if state == _State.PATH:
                if "=" not in arg:
                    result.path += f"/{arg}"
                else:
                    key, value = arg.split("=", 1)
                    result.path += f"/{{{key}}}"
                    result.path_variables[key] = value
                continue

            if state == _State.METHOD:
                result.method = arg.lower()
                state = _State.ARGS
                continue

            if state == _State.HEADER_KEY:
                key = arg
                result.headers[key] = ""
                state = _State.HEADER_VALUE
                continue
            if state == _State.HEADER_VALUE:
                result.headers[key] = arg
                state = _State.ARGS
                continue

            if state == _State.QUERY_KEY:
                key = arg
                result.queries[key] = ""
                state = _State.QUERY_VALUE
                continue
            if state == _State.QUERY_VALUE:
                result.queries[key] = arg
                state = _State.ARGS
                continue

            if state == _State.DATA:
                result.data = arg
                state = _State.ARGS
                continue

            if state == _State.FLAG:
                # TODO WHAT HERE????
                continue

            raise ParseError(f"Unhandled {arg} ({state.name}).")

        result._state = state
        return result

    def verify(self, query: Query) -> None:
        if query.path not in self.specification["paths"].keys():
            raise ValidationError(f"Path '{query.path}' is not valid.")

        for path_variable, value in query.path_variables.items():
            if not value:
                raise ValidationError(f"Path variable '{path_variable}' has not been set.")

        if not query.method:
            raise ValidationError("Method has not been set.")
        
        methods = self.specification["paths"][query.path].keys()
        if query.method not in methods:
            raise ValidationError(f"Method '{query.method}' is not supported.")

        parameters = self.specification["paths"][query.path][query.method]["parameters"]
        for param in [p for p in parameters if p["in"] == "header"]:
            if param["required"] and param["name"] not in query.headers.keys():
                raise ValidationError(f"Header '{param['name']}' has not been set.")
        for param in [p for p in parameters if p["in"] == "query"]:
            if param["required"] and param["name"] not in query.queries.keys():
                raise ValidationError(f"Query '{param['name']}' has not been set.")

        if any([p for p in parameters if p["in"] == "body"]) and not query.data:
            raise ValidationError("Data has not been set.")

        # TODO Verify the body structure

    def complete(self, args: list[str]) -> tuple[str]:
        query: Query = self.parse(args)

        if query._state == _State.PATH:
            # If the path is completely empty, ensure we have at least root
            if not query.path:
                query.path = "/"

            # If the parsed path contains filled in path variables, put them back
            for k, v in query.path_variables.items():
                query.path = query.path.replace(f"{{{k}}}", f"{k}={v}")

            path_stub: str = query.path.split("/")[-1]

            # Remove potentially incomplete path stub
            query.path = query.path.removesuffix(path_stub)

            sub = re.compile(r"\{(?P<domain>[\w]+)\}")

            # Find all paths matching the written one
            path: str
            paths: set[str] = set()
            for path in self.specification["paths"].keys():
                # If the parsed path contains filled in path variables, put them in
                for k, v in query.path_variables.items():
                    old = f"{{{k}}}"
                    new = f"{k}={v}"
                    path = path.replace(old, new)

                # For compeltion reasons, replace variables in paths
                #  - /dns/{domain}/a
                #  + /dns/domain=/a
                while "{" in path:
                    path = re.sub(sub, r"\g<domain>=", path)
                    # If the parsed path contains filled in path variables, put them back
                    for k, v in query.path_variables.items():
                        path = path.replace(f"{k=}", f"{k}={v}")

                # Skip paths that do not match what has been written already
                if not path.startswith(query.path + path_stub):
                    continue

                # Remove the part of the path that is completely written out
                path = path.removeprefix(query.path)

                # Only include direct children of the current path node
                path = path.split("/", 1)[0]

                paths.add(path)

            # Full path has been completed
            if not len(paths) or (len(paths) == 1 and tuple(paths)[0] == ""):
                query._state = _State.FLAG
                query.path = query.path.removesuffix("/")

            # There are children or partial children available
            if len(paths):
                return tuple(sorted(paths))

        # If the method is incomplete, push the state back
        if query._state == _State.ARGS:
            if query.method not in self.specification["paths"][query.path].keys():
                query._state = _State.METHOD

        if query._state == _State.FLAG:
            if not query.method:
                return ("-X", )
            query._state = _State.ARGS

        # If the header key is not complete, push the state back
        if query._state == _State.HEADER_VALUE:
            methods = self.specification["paths"][query.path]
            # Only move around if we know the method
            if query.method in methods.keys():
                params = [p["name"] for p in methods[query.method]["parameters"] if p["in"] == "header"]
                for key in params:
                    if key not in query.headers.keys():
                        # The header key is likely not complete yet
                        query._state = _State.HEADER_KEY

        # If the query key is not complete, push the state back
        if query._state == _State.QUERY_VALUE:
            methods = self.specification["paths"][query.path]
            # Only move around if we know the method
            if query.method in methods.keys():
                params = [p["name"] for p in methods[query.method]["parameters"] if p["in"] == "query"]
                for key in params:
                    if key not in query.headers.keys():
                        # The query key is likely not complete yet
                        query._state = _State.QUERY_KEY

        if query._state == _State.ARGS or query._state == _State.FLAG:
            # Until we know the method, we cannot decide which arguments are possible
            if not query.method:
                return ("-X", )

            # Suggest flags that are not yet filled in
            flags = set()
            for parameter in self.specification["paths"][query.path][query.method]["parameters"]:
                if parameter["in"] == "header" and parameter["name"] not in query.headers.keys():
                    flags.add("-H")
                    continue
                if parameter["in"] == "query" and parameter["name"] not in query.queries.keys():
                    flags.add("-Q")
                    continue
                if parameter["in"] == "body" and not query.data:
                    flags.add("-D")
                    continue
            
            return tuple(sorted(flags))

        if query._state == _State.METHOD:
            methods = self.specification["paths"][query.path].keys()
            if query.method:
                methods = [m for m in methods if m.startswith(query.method)]
            return tuple(sorted(methods))

        if query._state == _State.HEADER_KEY:
            # We cannot complete header keys if we don't know the method
            if not query.method:
                return tuple()

            keys = [
                p["name"]
                for p
                in self.specification["paths"][query.path][query.method]["parameters"]
                if p["in"] == "header" and p["name"] not in query.headers.keys()
            ]
            return tuple(sorted(keys))

        if query._state == _State.QUERY_KEY:
            # We cannot complete query keys if we don't know the method
            if not query.method:
                return tuple()

            keys = [
                p["name"]
                for p
                in self.specification["paths"][query.path][query.method]["parameters"]
                if p["in"] == "query" and p["name"] not in query.queries.keys()
            ]
            return tuple(sorted(keys))

        if query._state in (_State.HEADER_VALUE, _State.QUERY_VALUE, _State.DATA):
            return tuple()

        # TODO Completion for complex data types

        raise RuntimeError(f"Unhandled completion case: {query=} {query._state=}")
