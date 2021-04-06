#!/usr/bin/python3

import click
import logging
import os
import requests


@click.group()
def cli():
    pass


def get_headers():
    token = os.environ.get("BEARER_TOKEN")
    return {"Authorization": "Bearer {}".format(token)}


def get_proxies():
    proxies = {}
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies


def send_get_request(url: str, params: dict={}):
    response = requests.request(
        "GET", url, headers=get_headers(), params=params, proxies=get_proxies())
    while response.status_code != 200:
        logging.error("Request returned an error: {} {}".format(
            response.status_code, response.text))
        response = requests.request("GET", url, headers=headers, params=params)
    return response.json()


def get_favorite_tweets(username: str, max_search_number: int):
    url = "https://api.twitter.com/1.1/favorites/list.json?count={}&screen_name={}".format(
        max_search_number, username)
    return send_get_request(url)


def read_last_end_id(username: str):
    filename = '{}.last_end_id'.format(username)
    if not os.path.exists(filename):
        logging.error('{} not exists, will download all images.'.format(filename))
        return None
    with open(filename, 'r') as f:
        last_end_id = int(f.read())
        return last_end_id


def write_last_end_id(username: str, last_end_id: int):
    filename = '{}.last_end_id'.format(username)
    with open(filename, 'w') as f:
        f.write(str(last_end_id))


def download_image(output_dir: str, image_url: str):
    filename = image_url.split('/')[-1]
    output_path = os.path.join(output_dir, filename)
    if os.path.exists(output_path):
        logging.warning('{} already exists, skip.'.format(output_path))
        return
    orig_image_url = '{}?name=orig'.format(image_url)
    logging.info('Downloading image {} to {}'.format(orig_image_url, output_path))
    r = requests.get(orig_image_url, proxies=get_proxies())
    with open(output_path, "wb") as f:
        f.write(r.content)


@cli.command()
@click.option('--username', required=True, help="")
@click.option('--max_search_number', default=50, help="")
@click.option('--output_dir', default='./output/', help="")
@click.option('--log_path',
              default='./download_twitter_favorite_images.log',
              help="Path to output logging's log.")
def download(username, max_search_number, output_dir, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    last_end_id = read_last_end_id(username)
    logging.info('Download starts, last end id: {}'.format(last_end_id))
    image_urls = []

    favorite_tweets = get_favorite_tweets(username, max_search_number)
    for favorite_tweet in favorite_tweets:
        if favorite_tweet['id'] == last_end_id:
            logging.info('Meet last end id: {}, stop searching.'.format(last_end_id))
            break
        medias = favorite_tweet.get('extended_entities', {}).get('media', [])
        for media in medias:
            media_type = media.get('type', '')
            if media_type == 'photo':
                image_urls.append(media['media_url_https'])
            else:
                logging.error('Unsupport media type: {}, tweet url: {}'.format(
                    media_type, media['url']))

    for image_url in image_urls:
        download_image(output_dir, image_url)

    write_last_end_id(username, favorite_tweets[0]['id'])


if __name__ == "__main__":
    cli()
