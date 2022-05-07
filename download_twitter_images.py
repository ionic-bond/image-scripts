#!/usr/bin/python3

import click
import json
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


def send_get_request(url: str, params: dict = {}):
    response = requests.request(
        "GET", url, headers=get_headers(), params=params, proxies=get_proxies())
    while response.status_code != 200:
        logging.error("Request returned an error: {} {}".format(response.status_code,
                                                                response.text))
        response = requests.request(
            "GET", url, headers=get_headers(), params=params, proxies=get_proxies())
    return response.json()


def get_favorite_tweets(username: str):
    result = []
    url = "https://api.twitter.com/1.1/favorites/list.json?count=200&screen_name={}".format(
        username)
    favorite_tweets = send_get_request(url)
    result.extend(favorite_tweets)
    for _ in range(4):
        if not favorite_tweets:
            break
        min_id = min(favorite_tweet['id'] for favorite_tweet in favorite_tweets)
        print(min_id)
        url = "https://api.twitter.com/1.1/favorites/list.json?count=200&screen_name={}&max_id={}".format(
            username, min_id - 1)
        favorite_tweets = send_get_request(url)
        result.extend(favorite_tweets)
    print(len(result))
    return result


def read_prossesed_ids(username: str):
    processed_ids = set()
    filename = '{}.processed_ids'.format(username)
    if not os.path.exists(filename):
        logging.error('{} not exists, will download all images.'.format(filename))
        return processed_ids
    with open(filename, 'r') as f:
        for processed_id in f:
            processed_ids.add(int(processed_id))
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
    orig_image_url = '{}?name=orig'.format(image_url)
    print('Downloading image {} to {}'.format(orig_image_url, output_path))
    logging.info('Downloading image {} to {}'.format(orig_image_url, output_path))
    r = requests.get(orig_image_url, proxies=get_proxies())
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
            if len(splits) == 2 and splits[1] in ['jpg', 'png'] and len(splits[0]) == 15:
                existed_images.add(file_name)
    return existed_images


@cli.command()
@click.option('--username', required=True, help="")
@click.option('--output_dir', default='./output/', help="")
@click.option('--scan_dirs', default='./', help="")
@click.option(
    '--log_path', default='./download_user_like_images.log', help="Path to output logging's log.")
def download_user_like_images(username, output_dir, scan_dirs, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    processed_ids = read_prossesed_ids(username)
    logging.info('Processed ids num: {}'.format(len(processed_ids)))

    existed_images = set()
    for scan_dir in scan_dirs.split(','):
        existed_images = existed_images | get_existed_images(scan_dir)
    logging.info('existed images num: {}'.format(len(existed_images)))

    image_urls = []

    favorite_tweets = get_favorite_tweets(username)
    for favorite_tweet in favorite_tweets:
        if favorite_tweet['id'] in processed_ids:
            continue
        write_processed_id(username, favorite_tweet['id'])
        medias = favorite_tweet.get('extended_entities', {}).get('media', [])
        for media in medias:
            media_name = media['media_url_https'].split('/')[-1]
            if media_name in existed_images:
                continue
            media_type = media.get('type', '')
            if media_type != 'photo':
                logging.error('Unsupport media type: {}, tweet url: {}'.format(
                    media_type, media['url']))
                continue
            image_urls.append(media['media_url_https'])

    for image_url in image_urls:
        download_image(output_dir, image_url)


def get_tweets(username: str):
    result = []
    url = "https://api.twitter.com/1.1/statuses/user_timeline.json?count=200&screen_name={}&trim_user=false&include_rts=false".format(
        username)
    tweets = send_get_request(url)
    result.extend(tweets)
    while len(tweets):
        min_id = min(tweet['id'] for tweet in tweets)
        print(min_id)
        url = "https://api.twitter.com/1.1/statuses/user_timeline.json?count=200&screen_name={}&max_id={}&trim_user=false&include_rts=false".format(
            username, min_id - 1)
        tweets = send_get_request(url)
        result.extend(tweets)
    print(len(result))
    return result


@cli.command()
@click.option('--username', required=True, help="")
@click.option('--output_dir', default='./output/', help="")
@click.option(
    '--log_path', default='./download_user_tweet_images.log', help="Path to output logging's log.")
def download_user_tweet_images(username, output_dir, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    image_urls = []

    tweets = get_tweets(username)
    for tweet in tweets:
        medias = tweet.get('extended_entities', {}).get('media', [])
        for media in medias:
            media_type = media.get('type', '')
            if media_type != 'photo':
                print('Unsupport media type: {}, tweet url: {}'.format(media_type, media['url']))
                continue
            image_urls.append(media['media_url_https'])

    for image_url in image_urls:
        download_image(output_dir, image_url)


if __name__ == "__main__":
    cli()