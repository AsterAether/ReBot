from bs4 import BeautifulSoup
import conf
import os
import cv2
import imagehash
import re
import numpy as np

from skimage.measure import compare_ssim as ssim

from PIL import Image, ImageChops
import requests
from io import BytesIO
import pytesseract

pytesseract.pytesseract.tesseract_cmd = conf.tesseract_path
tessdata_dir_config = '--tessdata-dir "' + conf.tessdata_path + '"'
re_text = re.compile(r'[\W]+')


def image_perception_hash(filename):
    phash = imagehash.phash(Image.open('files/' + filename))
    return str(phash)


# def phash_distance(phash1, phash2):
#     dist = 1 - bitcount(phash1 ^ phash2) / 64.0


def image_trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()

    if bbox:
        return im.crop(bbox)


def compare_image_ssim(filename1, filename2):
    image1 = cv2.imread('files/' + filename1)
    image2 = cv2.imread('files/' + filename2)
    height, width = image1.shape[:2]
    image2 = cv2.resize(image2, (width, height))
    return ssim(image1, image2, multichannel=True)


def image_to_string(filename):
    image = cv2.imread('files/' + filename)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # gray = cv2.threshold(gray, 0, 255,
    #                      cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    gray = cv2.medianBlur(gray, 3)

    tmp_filename = 'tmp/{}.png'.format(os.getpid())
    cv2.imwrite(tmp_filename, gray)

    text = pytesseract.image_to_string(Image.open(tmp_filename), config=tessdata_dir_config)
    text = re_text.sub(' ', text)
    return text


def handle_url_image(url, filename):
    response = requests.get(url)
    if 'image' in response.headers.get('Content-Type'):
        content_type = response.headers.get('Content-Type')
        img = get_image_from_response(response)
        path = 'files/' + filename + '.' + content_type.replace('image/', '')
        img.save(path)
        return filename + '.' + content_type.replace('image/', '')
    else:
        soup = BeautifulSoup(response.text, 'html.parser')
        image_meta = soup.find('meta', property="og:image")
        if image_meta:
            response = requests.get(image_meta.get('content'))
            img = get_image_from_response(response)
            content_type = response.headers.get('Content-Type')
            path = 'files/' + filename + '.' + content_type.replace('image/', '')
            img.save(path)
            return filename + '.' + content_type.replace('image/', '')
        else:
            return None


def get_image_from_response(response):
    content_type = response.headers.get('Content-Type')
    if 'image' in content_type:
        img = Image.open(BytesIO(response.content))
        return img
    else:
        return None
