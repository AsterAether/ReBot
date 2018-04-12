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
re_text = re.compile(r'[^A-Za-z0-9]+')


def image_perception_hash(filename):
    phash = imagehash.phash(Image.open('files/' + filename))
    return str(phash)


# def phash_distance(phash1, phash2):
#     dist = 1 - bitcount(phash1 ^ phash2) / 64.0


def image_crop(filename):
    try:
        filename = 'files/' + filename

        # Load the image in black and white (0 - b/w, 1 - color).
        img = cv2.imread(filename, 0)

        # Get the height and width of the image.
        h, w = img.shape[:2]

        # Invert the image to be white on black for compatibility with findContours function.
        imgray = 255 - img
        # Binarize the image and call it thresh.
        ret, thresh = cv2.threshold(imgray, 127, 255, cv2.THRESH_BINARY)

        # Find all the contours in thresh. In your case the 3 and the additional strike
        _, contours, hierarchy = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        # Calculate bounding rectangles for each contour.
        rects = [cv2.boundingRect(cnt) for cnt in contours]

        # Calculate the combined bounding rectangle points.
        top_x = min([x for (x, y, w, h) in rects])
        top_y = min([y for (x, y, w, h) in rects])
        bottom_x = max([x + w for (x, y, w, h) in rects])
        bottom_y = max([y + h for (x, y, w, h) in rects])

        # Draw the rectangle on the image
        # out = cv2.rectangle(img, (top_x, top_y), (bottom_x, bottom_y), (0, 255, 0), 2)
        img = cv2.imread(filename)
        img = img[top_y:bottom_y, top_x:bottom_x]
        # Save it as out.jpg
        cv2.imwrite(filename, img)
    except:
        print(filename + ' ERROR CROPPING')


def compare_image_ssim(filename1, filename2):

    print(filename1 + ' vs ' + filename2)

    image1 = cv2.imread('files/' + filename1)
    image2 = cv2.imread('files/' + filename2)
    height1, width1 = image1.shape[:2]
    height2, width2 = image1.shape[:2]
    size_1 = (height1 * width1, image2, image1, height1, width1)
    size_2 = (height2 * width2, image1, image2, height2, width2)

    size = min([size_1, size_2], key=lambda s: s[0])

    img = cv2.resize(size[1], (size[4], size[3]))
    cv2.imwrite('res.jpg', img)
    return ssim(size[2], img, multichannel=True)


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
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException:
        return None

    if 'image' in response.headers.get('Content-Type') and 'gif' not in response.headers.get('Content-Type'):
        content_type = response.headers.get('Content-Type')
        img = get_image_from_response(response)
        path = 'files/' + filename + '.' + content_type.replace('image/', '')
        img.save(path)
        return filename + '.' + content_type.replace('image/', '')
    else:
        soup = BeautifulSoup(response.text, 'html.parser')
        image_meta = soup.find('meta', property="og:image")
        if image_meta:
            if 'gif' in image_meta.get('content'):
                return None
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


if __name__ == '__main__':
    print(compare_image_ssim('img1.jpg', 'img2.jpg'))
