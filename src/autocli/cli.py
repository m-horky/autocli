import argparse
import os
import shutil
import subprocess
import sys
import logging
import pathlib
import tempfile


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
    specification: str
    package: str

    def __init__(self):
        parser = self._get_parser()
        args = parser.parse_args()

        self.name: str = args.name
        self.specification: str = args.specification
        self.package = self.name.replace("-", "_")

        self._build_dir: pathlib.Path = (
            pathlib.Path(args.build_dir.format(name=self.name))
            if "{name}" in args.build_dir
            else pathlib.Path(args.build_dir)
        )
        self._package_dir = self._build_dir / "src" / self.package
        self._tmp_dir = pathlib.Path("/tmp/autocli/")

    def run(self):
        # self._ensure_directories()
        # self._pull_container()
        # self._run_container()
        self._generate_init_py()
        self._generate_about_py()
        self._generate_pyproject_toml()
        self._extract_generated_library()

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

    def _pull_container(self) -> None:
        log.info("fetching container image")
        cmd_fetch: subprocess.CompletedProcess = subprocess.run(
            ["podman", "pull", "docker.io/swaggerapi/swagger-codegen-cli"],
            capture_output=True,
        )
        if cmd_fetch.returncode != 0:
            log.critical(
                "could not pull container image\n"
                + "stdout:\n"
                + cmd_fetch.stdout.decode("utf-8")
                + "stderr:\n"
                + cmd_fetch.stderr.decode("utf-8")
            )
            sys.exit(1)

    def _run_container(self) -> None:
        log.info("generating the library from API specification")
        cmd_gen: subprocess.CompletedProcess = subprocess.run(
            [
                "podman",
                "run",
                "--rm",
                "-v",
                f"{self._tmp_dir.absolute()!s}:/local/out/py",
                "swaggerapi/swagger-codegen-cli:latest",
                "generate",
                "-i",
                self.specification,
                "-l",
                "python",
                "-o",
                "/local/out/py",
            ],
            capture_output=True,
        )
        if cmd_gen.returncode != 0:
            log.critical(
                "could not generate the library\n"
                + "stdout:\n"
                + cmd_gen.stdout.decode("utf-8")
                + "stderr:\n"
                + cmd_gen.stderr.decode("utf-8")
            )
            sys.exit(1)

    def _generate_init_py(self):
        log.info("generating __init__.py")
        with (self._package_dir / "__init__.py").open("w") as f:
            f.write("")

    def _generate_about_py(self):
        log.info("generating __about__.py")
        with (self._package_dir / "__about__.py").open("w") as f:
            f.writelines(
                [
                    # TODO Include the API version in the field
                    "VERSION = '0.0.0+0.0.0'\n",
                ]
            )

    def _generate_pyproject_toml(self):
        log.info("generating pyproject.toml")

        requirements: list[str] = []
        if (reqs := (self._tmp_dir / "requirements.txt")).exists():
            with reqs.open("r") as f:
                requirements = [
                    f"\t'{requirement.strip()}',\n" for requirement in f.readlines()
                ]
        test_requirements: list[str] = []
        if (reqs := (self._tmp_dir / "test-requirements.txt")).exists():
            with reqs.open("r") as f:
                test_requirements = [
                    f"\t'{requirement.strip()}',\n" for requirement in f.readlines()
                ]

        with (self._build_dir / "pyproject.toml").open("w") as f:
            f.writelines(
                [
                    "[build-system]\n",
                    "requires = ['setuptools']\n",
                    "\n",
                    "[project]\n",
                    f"name = '{self.name}'\n",
                    "authors = [{ name = 'example', email = 'example@example.org' }]\n",
                    "description = 'Autogenerated CLI tool'\n",
                    "keywords = ['OpenAPI', 'Swagger']\n",
                    "license = { text = 'MIT' }\n",
                    "dynamic = ['version']\n",
                    "dependencies = [\n",
                    *requirements,
                    "]\n",
                    "requires-python = '>=3.9'\n",
                    "\n",
                    "[project.optional-dependencies]\n",
                    "test = [\n",
                    *test_requirements,
                    "]\n",
                    "\n",
                    "[project.scripts]\n",
                    f"{self.name} = '{self.package}.cli:main'\n",
                    "\n",
                    "[tool.setuptools.dynamic]\n",
                    f"version = {{ attr = '{self.package}.__about__.VERSION' }}\n",
                ]
            )

    def _extract_generated_library(self):
        log.info("copying autogenerated library code")
        # TODO Uncomment
        # shutil.move(self._tmp_dir / "swagger_client", self._package_dir)
        # os.rename(self._package_dir / "swagger_client", self._package_dir / "auto")

        log.debug("fixing import statements")
        for file in (self._package_dir / "auto").glob("**/*.py"):
            with file.open("r") as f:
                lines = f.readlines()

            with file.open("w") as f:
                for line in lines:
                    if "swagger_client" in line:
                        line = line.replace("swagger_client", f"{self.package}.auto")
                    f.write(line)


def main():
    g = CLIGenerator()
    g.run()
    # TODO Generate {self.package}.cli:main


if __name__ == "__main__":
    main()
