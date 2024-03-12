#!/usr/bin/python3

import os

import click


@click.group()
def cli():
    pass


def _is_image(filename):
    f = filename.lower()
    return f.endswith(".png") or f.endswith(".jpg") or \
        f.endswith(".jpeg") or f.endswith(".bmp") or \
        f.endswith(".gif") or '.jpg' in f or  f.endswith(".svg")


@cli.command()
@click.option('--base_dir', required=True, help="")
@click.option('--scan_dir', required=True, help="")
def run(base_dir, scan_dir):
    base_dict = dict()
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if _is_image(file):
                path = os.path.join(root, file).replace('\\', '/')
                base_dict[file] = {'path': path, 'size': os.path.getsize(path)}

    for root, dirs, files in os.walk(scan_dir):
        for file in files:
            if file in base_dict:
                details = base_dict[file]
                path = os.path.join(root, file).replace('\\', '/')
                if details['path'] != path and details['size'] == os.path.getsize(path):
                    os.remove(path)
                    print('Removed {}'.format(path))


if __name__ == "__main__":
    cli()
