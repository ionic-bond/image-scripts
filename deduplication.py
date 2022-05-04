#!/usr/bin/python3

import os
import re

import click
import imagehash
from PIL import Image

PIXIV_PATTERN = re.compile(r'\d+_p\d+')

@click.group()
def cli():
    pass

def _is_image(filename):
    f = filename.lower()
    return f.endswith(".png") or f.endswith(".jpg") or \
        f.endswith(".jpeg") or f.endswith(".bmp") or \
        f.endswith(".gif") or '.jpg' in f or  f.endswith(".svg")

def _is_pximg(img_path):
    file_name = os.path.basename(img_path)
    file_name = file_name.split('.')[0]
    return bool(PIXIV_PATTERN.match(file_name))

def _is_twimg(img_path):
    file_name = os.path.basename(img_path)
    file_name = file_name.split('.')[0]
    return len(file_name) == 15

def _filter(img_list):
    print(' '.join(img_list))
    pximg_size = None
    for img_path in img_list:
        if _is_pximg(img_path):
            pximg_size = os.path.getsize(img_path)
    if pximg_size:
        for img_path in img_list:
            if _is_twimg(img_path):
                if os.path.getsize(img_path) < pximg_size:
                    os.remove(img_path)
                    print('removed {}'.format(img_path))
        

@cli.command()
@click.option('--scan_dir', required=True, help="")
def run(scan_dir):
    image_filenames = [os.path.join(scan_dir, path) for path in os.listdir(scan_dir) if _is_image(path)]
    images = {}
    for img in sorted(image_filenames):
        try:
            hash = imagehash.whash(Image.open(img))
        except Exception as e:
            print('Problem:', e, 'with', img)
            continue
        images[hash] = images.get(hash, []) + [img]

    for img_list in images.values():
        if len(img_list) > 1:
            _filter(img_list)

if __name__ == "__main__":
    cli()