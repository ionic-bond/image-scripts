#!/usr/bin/python3

import click
import json
import logging
import os
import pixivpy3
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


def get_refresh_token():
    refresh_token = os.environ.get('PIXIV_REFRESH_TOKEN')
    assert refresh_token
    return refresh_token


def get_api():
    api = pixivpy3.ByPassSniApi()
    api.require_appapi_hosts(hostname='210.140.131.223')
    api.set_accept_language("en-us")
    api.auth(refresh_token=get_refresh_token())
    return api


def get_user_bookmarks_illust(api, user_id):
    result = []
    page_result = api.user_bookmarks_illust(user_id, restrict="public")
    result.extend(page_result['illusts'])
    while page_result['next_url']:
        next_qs = api.parse_qs(page_result['next_url'])
        assert next_qs
        page_result = api.user_bookmarks_illust(**next_qs)
        result.extend(page_result['illusts'])
    return result


def get_user_illust(api, user_id):
    result = []
    page_result = api.user_illusts(user_id, type="illust")
    result.extend(page_result['illusts'])
    while page_result['next_url']:
        next_qs = api.parse_qs(page_result['next_url'])
        assert next_qs
        page_result = api.user_illusts(**next_qs)
        result.extend(page_result['illusts'])
    return result


def get_image_urls_from_illust(illust):
    assert illust['meta_single_page'] or illust['meta_pages']
    assert not (illust['meta_single_page'] and illust['meta_pages'])
    if illust['meta_single_page']:
        return [illust['meta_single_page']['original_image_url']]
    else:
        return [meta_page['image_urls']['original'] for meta_page in illust['meta_pages']]


def read_prossesed_ids(username: str):
    processed_ids = set()
    filename = '{}.processed_ids'.format(username)
    if not os.path.exists(filename):
        logging.error('{} not exists, will download all images.'.format(filename))
        return processed_ids
    with open(filename, 'r') as f:
        for processed_id in f:
            processed_ids.add(processed_id.rstrip('\r\n'))
    return processed_ids


def write_processed_id(username: str, processed_id: int):
    filename = '{}.processed_ids'.format(username)
    with open(filename, 'a') as f:
        f.write('{}\n'.format(str(processed_id)))


def download_image(output_dir: str, image_url: str):
    filename = image_url.split('/')[-1]
    output_path = os.path.join(output_dir, filename)
    if os.path.exists(output_path):
        logging.warning('{} already exists, skip.'.format(output_path))
        return
    print('Downloading image {} to {}'.format(image_url, output_path))
    logging.info('Downloading image {} to {}'.format(image_url, output_path))
    r = requests.get(
        image_url,
        proxies=get_proxies(),
        headers={
            'Referer':
                'https://www.pixiv.net/',
            'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
        })
    with open(output_path, "wb") as f:
        f.write(r.content)


def get_existed_images(scan_dir: str):
    existed_images = set()
    for file_name in os.listdir(scan_dir):
        file_path = os.path.join(scan_dir, file_name)
        if os.path.isdir(file_path):
            existed_images = existed_images | get_existed_images(file_path)
        else:
            splits = file_name.split('.')
            if len(splits) == 2 and splits[1] in ['jpg', 'png'] and '_p' in splits[0]:
                existed_images.add(file_name)
    return existed_images


@cli.command()
@click.option('--user_id', required=True, help="")
@click.option('--output_dir', default='./output/', help="")
@click.option('--scan_dirs', default='./', help="")
@click.option('--log_path',
              default='./download_user_bookmarks_images.log',
              help="Path to output logging's log.")
def download_user_bookmarks_images(user_id, output_dir, scan_dirs, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    processed_ids = read_prossesed_ids(user_id)
    logging.info('Processed ids num: {}'.format(len(processed_ids)))

    existed_images = set()
    for scan_dir in scan_dirs.split(','):
        existed_images = existed_images | get_existed_images(scan_dir)
    logging.info('existed images num: {}'.format(len(existed_images)))

    image_urls = []

    api = get_api()
    illusts = get_user_bookmarks_illust(api, user_id)
    for illust in illusts:
        urls = get_image_urls_from_illust(illust)
        for url in urls:
            image_file_name = url.split('/')[-1]
            image_id = image_file_name.split('.')[0]
            if image_id in processed_ids:
                continue
            write_processed_id(user_id, image_id)
            if image_file_name in existed_images:
                continue
            image_urls.append(url)

    for image_url in image_urls:
        download_image(output_dir, image_url)


@cli.command()
@click.option('--user_id', required=True, help="")
@click.option('--output_dir', default='./output/', help="")
@click.option('--log_path',
              default='./download_user_images.log',
              help="Path to output logging's log.")
def download_user_images(user_id, output_dir, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    api = get_api()
    illusts = get_user_illust(api, user_id)
    for illust in illusts:
        urls = get_image_urls_from_illust(illust)
        for url in urls:
            download_image(output_dir, url)


if __name__ == "__main__":
    cli()
