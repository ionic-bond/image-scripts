#!/usr/bin/python3

import click
import json
import logging
import os
import time
from collections import deque

import requests

from graphql_api import GraphqlAPI
from login import login


@click.group()
def cli():
    pass


cookie_path = ''


def get_proxies():
    proxies = {}
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy:
        proxies["https"] = https_proxy
    return proxies


def get_headers(headers, cookies) -> dict:
    authed_headers = headers | {
        'cookie': '; '.join(f'{k}={v}' for k, v in cookies.items()),
        'referer': 'https://twitter.com/',
        'x-csrf-token': cookies.get('ct0', ''),
        'x-guest-token': cookies.get('guest_token', ''),
        'x-twitter-auth-type': 'OAuth2Session' if cookies.get('auth_token') else '',
        'x-twitter-active-user': 'yes',
        'x-twitter-client-language': 'en',
    }
    return dict(sorted({k.lower(): v for k, v in authed_headers.items()}.items()))


def build_params(params: dict) -> dict:
    return {k: json.dumps(v) for k, v in params.items()}


def find_all(obj: any, key: str) -> list:
    # DFS
    def dfs(obj: any, key: str, res: list) -> list:
        if not obj:
            return res
        if isinstance(obj, list):
            for e in obj:
                res.extend(dfs(e, key, []))
            return res
        if isinstance(obj, dict):
            if key in obj:
                res.append(obj[key])
            for v in obj.values():
                res.extend(dfs(v, key, []))
        return res

    return dfs(obj, key, [])


def find_one(obj: any, key: str) -> any:
    # BFS
    que = deque([obj])
    while len(que):
        obj = que.popleft()
        if isinstance(obj, list):
            que.extend(obj)
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                que.append(v)
    return None


def get_cursor(obj: any) -> str:
    entries = find_one(obj, 'entries')
    for entry in entries:
        entry_id = entry.get('entryId', '')
        if entry_id.startswith('cursor-bottom'):
            return entry.get('content', {}).get('value', '')


def send_get_request(api_name: str, params: dict = {}):
    with open(cookie_path, 'r') as f:
        cookies = json.load(f)
    url, _, headers, features = GraphqlAPI.get_api_data(api_name)
    headers = get_headers(headers, cookies)
    params = build_params({"variables": params, "features": features})
    response = requests.request("GET", url, params=params, headers=headers, proxies=get_proxies())
    while response.status_code != 200:
        logging.error("Request returned an error: {} {}".format(response.status_code,
                                                                response.text))
        time.sleep(5)
        response = requests.request("GET",
                                    url,
                                    params=params,
                                    headers=headers,
                                    proxies=get_proxies())
    return response.json()


def get_id_by_username(username: str):
    api_name = 'UserByScreenName'
    params = {'screen_name': username}
    json_response = send_get_request(api_name, params)
    while json_response is None:
        time.sleep(10)
        json_response = send_get_request(api_name, params)
    return find_one(json_response, 'rest_id')


def get_favorite_tweets(username: str):
    result = []
    user_id = get_id_by_username(username)
    api_name = 'Likes'
    params = {'userId': user_id, 'includePromotedContent': True, 'count': 1000}
    json_response = send_get_request(api_name, params)
    favorite_tweets = find_all(json_response, 'tweet_results')
    result.extend(favorite_tweets)
    while len(result) < 500:
        cursor = get_cursor(json_response)
        if not cursor or cursor.startswith('-1|') or cursor.startswith('0|'):
            break
        params['cursor'] = cursor
        json_response = send_get_request(api_name, params)
        favorite_tweets = find_all(json_response, 'tweet_results')
        result.extend(favorite_tweets)
    return result


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
@click.option('--auth_cookie_path', required=True)
@click.option('--output_dir', default='./output/', help="")
@click.option('--scan_dirs', default='./', help="")
@click.option('--exclude_users', default='', help="")
@click.option('--log_path',
              default='./download_user_like_images.log',
              help="Path to output logging's log.")
def download_user_like_images(username, auth_cookie_path, output_dir, scan_dirs, exclude_users,
                              log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    global cookie_path
    cookie_path = auth_cookie_path

    processed_ids = read_prossesed_ids(username)
    logging.info('Processed ids num: {}'.format(len(processed_ids)))

    existed_images = set()
    for scan_dir in scan_dirs.split(','):
        existed_images = existed_images | get_existed_images(scan_dir)
    logging.info('existed images num: {}'.format(len(existed_images)))

    exclude_users = exclude_users.split(',') if exclude_users else []

    image_urls = []

    favorite_tweets = get_favorite_tweets(username)
    for favorite_tweet in favorite_tweets:
        user = find_one(favorite_tweet, 'user_results')
        like_username = find_one(user, 'screen_name')
        if like_username in exclude_users:
            continue
        if find_one(favorite_tweet, 'rest_id') in processed_ids:
            continue
        write_processed_id(username, find_one(favorite_tweet, 'rest_id'))
        extended_entities = find_one(favorite_tweet, 'extended_entities')
        if not extended_entities:
            continue
        medias = extended_entities.get('media', [])
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
    user_id = get_id_by_username(username)
    api_name = 'UserMedia'
    params = {'userId': user_id, 'includePromotedContent': True, 'withVoice': True, 'count': 1000}
    json_response = send_get_request(api_name, params)
    tweets = find_all(json_response, 'tweet_results')
    result.extend(tweets)
    while tweets:
        cursor = get_cursor(json_response)
        if not cursor or cursor.startswith('-1|') or cursor.startswith('0|'):
            break
        params['cursor'] = cursor
        json_response = send_get_request(api_name, params)
        tweets = find_all(json_response, 'tweet_results')
        result.extend(tweets)
        print(len(result))
    return result


@cli.command()
@click.option('--username', required=True, help="")
@click.option('--auth_cookie_path', required=True)
@click.option('--output_dir', default='./output/', help="")
@click.option('--log_path',
              default='./download_user_tweet_images.log',
              help="Path to output logging's log.")
def download_user_tweet_images(username, auth_cookie_path, output_dir, log_path):
    logging.basicConfig(filename=log_path, format='%(asctime)s - %(message)s', level=logging.INFO)
    os.makedirs(output_dir, exist_ok=True)

    global cookie_path
    cookie_path = auth_cookie_path

    image_urls = []

    tweets = get_tweets(username)
    for tweet in tweets:
        extended_entities = find_one(tweet, 'extended_entities')
        if not extended_entities:
            continue
        medias = extended_entities.get('media', [])
        for media in medias:
            media_type = media.get('type', '')
            if media_type != 'photo':
                print('Unsupport media type: {}, tweet url: {}'.format(media_type, media['url']))
                continue
            image_urls.append(media['media_url_https'])

    for image_url in image_urls:
        download_image(output_dir, image_url)


@cli.command()
@click.option('--username', required=True)
@click.option('--password', required=True)
def generate_auth_cookie(username, password):
    client = login(username=username, password=password)
    cookies = client.cookies
    dump_path = '{}.json'.format(username)
    with open(dump_path, 'w') as f:
        f.write(json.dumps(dict(cookies), indent=2))
    print('Saved to {}'.format(dump_path))


if __name__ == "__main__":
    cli()
