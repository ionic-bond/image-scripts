#!/usr/bin/python3

import click
import logging
import os
import requests


@click.group()
def cli():
    pass


def get_proxies():
    proxies = {}
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies


def check_image(file_dir, file_name):
    file_path = os.path.join(file_dir, file_name)
    split = file_name.split('.')
    if len(split) != 2:
        logging.error('Unknow file: {}'.format(file_path))
        return
    if split[1] not in ['jpg', 'png']:
        logging.error('Unknow format: {} {}'.format(file_path, len(split[0])))
        return
    if len(split[0]) != 15:
        return

    orig_image_url = r"https://pbs.twimg.com/media/{}?name=orig".format(file_name)
    r = requests.get(orig_image_url, proxies=get_proxies())
    old_size = os.path.getsize(file_path)
    new_size = len(r.content)
    if old_size > new_size:
        logging.error('{} ({}), {} ({})'.format(file_path, old_size, orig_image_url, new_size))
    if old_size >= new_size:
        return
    logging.info('Replace {} ({}) with {} ({})'.format(file_path, old_size, orig_image_url, new_size))
    with open(file_path, "wb") as f:
        f.write(r.content)


def scan(scan_dir):
    for file_name in os.listdir(scan_dir):
        file_path = os.path.join(scan_dir, file_name)
        if os.path.isdir(file_path):
            scan(file_path)
        else:
            check_image(scan_dir, file_name)


@cli.command()
@click.option('--scan_dir', default='./', help="")
@click.option('--log_path',
              default='./update_twitter_image_to_original_size.log',
              help="Path to output logging's log.")
def check(scan_dir, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    scan(scan_dir)


if __name__ == "__main__":
    cli()
