import functools
import logging
from typing import Any


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)8s "
    "%(module)s:%(funcName)s:%(lineno)s | %(message)s",
)
log = logging.getLogger(__file__)


class AutoTool:
    def __init__(self, specification: dict):
        self.specification = specification

    @functools.cache
    def paths(self) -> dict[str, Any]:
        """Parse the API specification and obtain a tree of API paths.

        The result is a tree of API path sections with `None` as leafs.
        """
        log.debug("computing the API path tree")
        paths: dict = {}
        for path in self.specification.get("paths", {}).keys():
            currpath = paths
            sections = path.strip("/").split("/")
            for i, section in enumerate(sections, 1):
                if section not in currpath:
                    if i == len(sections):
                        currpath[section] = None
                    else:
                        currpath[section] = {}
                currpath = currpath[section]
        return paths

    def path_methods(self, *args) -> set[str]:
        """Obtain possible HTTP methods for given path."""
        path: str = "/" + "/".join(args)

        try:
            methods: dict = self.specification["paths"][path]
        except KeyError:
            raise ValueError(f"no such path: {path}")
        return set(methods.keys())

    def complete_path(self, *args) -> set[str]:
        """Offer a list of completions for a path.

        When no further path sections are not available, an empty set is returned.

        When some path does not exist, a ValueError is raised.
        """
        location = self.paths()
        for arg in args:
            if arg not in location:
                raise ValueError(f"no such path: {arg} does not exist in {location}")
            location = location[arg]

        if location is not None:
            return set(location.keys())
        return set()
