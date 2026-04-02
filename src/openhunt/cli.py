import click

from openhunt import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """openhunt - automate your job search on hh.ru."""


if __name__ == "__main__":
    main()
