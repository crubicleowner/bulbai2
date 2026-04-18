from bulbopt import PACKAGE_NAME, __version__


def build_cli_banner() -> str:
    return f"{PACKAGE_NAME} {__version__} | STL-first vertical slice"


if __name__ == "__main__":
    print(build_cli_banner())