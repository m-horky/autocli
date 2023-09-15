import argparse
import shutil
import sys
import logging
import pathlib
import requests
from typing import Optional


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)8s "
    "%(module)s:%(funcName)s:%(lineno)s | %(message)s",
)
log = logging.getLogger(__file__)


class CLIGenerator:
    _build_dir: pathlib.Path
    _package_dir: pathlib.Path
    _auto_dir: pathlib.Path
    _tmp_dir: pathlib.Path

    name: str
    specification_url: str
    api_url: str
    package: str

    def __init__(self, args: Optional[argparse.Namespace] = None):
        if args is None:
            parser = self._get_parser()
            args = parser.parse_args()

        self.name: str = args.name
        self.specification_url: str = args.specification
        self.api_url: str = args.address
        self.package = self.name.replace("-", "_")

        self._build_dir: pathlib.Path = (
            pathlib.Path(args.build_dir.format(name=self.name))
            if "{name}" in args.build_dir
            else pathlib.Path(args.build_dir)
        )
        self._package_dir = self._build_dir / "src" / self.package
        self._tmp_dir = pathlib.Path("/tmp/autocli/")

    def run(self):
        self._ensure_directories()
        self._download_specification()
        self._copy_autolib()
        self._generate_pyproject_toml()
        self._generate_init_py()
        self._generate_about_py()

    def _get_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "name",
            help="name of the project (preferably with '-cli' suffix)",
        )
        parser.add_argument(
            "specification",
            help="URL pointing to the JSON OpenAPI specification",
        )
        parser.add_argument(
            "address",
            help="URL pointing to the API itself",
        )
        parser.add_argument(
            "--build-dir",
            required=False,
            help="path to build directory",
            default="./build/{name}",
        )
        parser.add_argument(
            "-f",
            "--force",
            help="overwrite the previous autogenerated data",
            action="store_true",
        )
        return parser

    def _ensure_directories(self) -> None:
        # Create build directory for the project
        log.debug(f"ensuring directory {self._build_dir!s}")
        self._build_dir.mkdir(exist_ok=True, parents=True)
        (self._build_dir / "src").mkdir(exist_ok=True)

        self._package_dir.mkdir(exist_ok=True)

        # Create temporary directory for autogenerated code
        shutil.rmtree(self._tmp_dir.absolute(), ignore_errors=True)
        self._tmp_dir.mkdir()
    
    def _copy_autolib(self):
        log.info("vendorising autolib into the package")
        autolib_init = pathlib.Path(__file__).parent.parent / "autolib" / "__init__.py"
        autolib_path = pathlib.Path(self._package_dir / "autolib.py")
        shutil.copy(autolib_init, autolib_path)

    def _generate_init_py(self):
        log.info("generating __init__.py")
        with (self._package_dir / "__init__.py").open("w") as f:
            f.write("\n".join([
                "#!/usr/bin/env python3",
                "",
                "import sys",
                "import logging",
                "",
                f"import {self.package}.__about__",
                f"from {self.package} import autolib",
                "",
                "",
                f"TOOL = autolib.AutoTool({self.package}.__about__.SPECIFICATION)",
                "",
                "",
                "def complete():",
                "    for suggestion in sorted(TOOL.complete(sys.argv[2:])):",
                "        print(suggestion)",
                "",
                "",
                "def main():",
                "    logging.basicConfig(",
                "        level=logging.DEBUG,",
                '        format="%(asctime)s %(levelname)8s "',
                '        "%(module)s:%(funcName)s:%(lineno)s | %(message)s",',
                '    )',
                f'    TOOL.run({self.package}.__about__.API_URL, sys.argv[1:])',
                "",
            ]))

    def _generate_about_py(self):
        log.info("generating __about__.py")
        with (self._package_dir / "__about__.py").open("w") as f:
            f.writelines(
                [
                    # TODO Include the API version in the field
                    "VERSION = '0.0.0+0.0.0'\n",
                    f"SPECIFICATION_URL = '{self.specification_url}'\n"
                    f"API_URL = '{self.api_url}'\n"
                    f"SPECIFICATION = {self.specification!s}\n",
                ]
            )

    def _generate_pyproject_toml(self):
        log.info("generating pyproject.toml")
        with (self._build_dir / "pyproject.toml").open("w") as f:
            f.write("\n".join([
                "[build-system]",
                "requires = ['setuptools']",
                "",
                "[project]",
                f"name = '{self.name}'",
                "authors = [{ name = 'example', email = 'example@example.org' }]",
                "description = 'Autogenerated CLI tool'",
                "keywords = ['OpenAPI', 'Swagger']",
                "license = { text = 'MIT' }",
                "dynamic = ['version']",
                "dependencies = [",
                "    'requests',",
                "]",
                "requires-python = '>=3.9'",
                "",
                "[project.optional-dependencies]",
                "test = [",
                "]",
                "",
                "[project.scripts]",
                f"{self.name} = '{self.package}:main'",
                "",
                "[tool.setuptools.dynamic]",
                f"version = {{ attr = '{self.package}.__about__.VERSION' }}",
            ]))

    def _download_specification(self) -> None:
        log.info("downloading API specification")
        req = requests.get(self.specification_url)
        if req.status_code != 200:
            log.critical(f"got status code {req.status_code}")
            sys.exit(1)

        try:
            self.specification = req.json()
        except Exception as exc:
            log.critical(f"could not parse JSON: {exc}", exc_info=True)
            sys.exit(1)
    
    def _print_non_pipx(self) -> None:
        print()
        print("To use the autogenerated CLI, run")
        print("\033[1;33m", end="")
        print(f"python3 -m pip install -e build/{self.name}")
        print("_{name}() {{".format(name=self.name))
        print("\t" + r"local cur=${COMP_WORDS[COMP_CWORD]}")
        print("\tlocal OPTIONS=`python3 -c 'import {package}; {package}.complete()' \"${{COMP_WORDS[@]}}\"`".format(package=self.package))
        print("\tCOMPREPLY=( $( compgen -W \"${OPTIONS}\" -- \"$cur\" ) )")
        print("\treturn 0")
        print("}")
        print("complete -F _{name} {name}".format(name=self.name))
        print("\033[0;0m", end="")

    def _print_pipx(self) -> None:
        if shutil.which("pipx") is None:
            return

        print()
        print("You have \033[4mpipx\033[0m available. The easiest way to install the package is:\033[0m")
        print("\033[1;33m", end="")
        print(f"pipx install {self._build_dir.absolute()}")
        print("_{name}() {{".format(name=self.name))
        print("\t" + r"local cur=${COMP_WORDS[COMP_CWORD]}")
        print("\tlocal OPTIONS=`$HOME/.local/pipx/venvs/{name}/bin/python3 -c 'import {package}; {package}.complete()' \"${{COMP_WORDS[@]}}\"`".format(name=self.name, package=self.package))
        print("\tCOMPREPLY=( $( compgen -W \"${OPTIONS}\" -- \"$cur\" ) )")
        print("\treturn 0")
        print("}")
        print("complete -F _{name} {name}".format(name=self.name))
        print("\033[0;0m", end="")



def main():
    g = CLIGenerator()
    g.run()

    g._print_non_pipx()
    g._print_pipx()
    


if __name__ == "__main__":
    main()