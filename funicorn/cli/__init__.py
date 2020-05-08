import click

common_options = [
    click.option('-h', '--host', default='0.0.0.0', show_default=True,
                 help='funicorn service host.'),
    click.option('-p', '--port', required=True, show_default=True,
                 type=int, help='funicorn service port.')
]


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


@click.command()
@add_options(common_options)
def terminate(host, port):
    print(f"{host}:{port} to use in terminate")


@click.command()
@add_options(common_options)
def restart(host, port):
    print(f"{host}:{port} to use in restart")


@click.command()
@add_options(common_options)
def idle(host, port):
    print(f"{host}:{port} to use in idle")


def start(port, host):
    pass
