import io

import pytest
from PIL import Image

from m5view_sender import imageprep


@pytest.mark.parametrize("fit", imageprep.FIT_MODES)
@pytest.mark.parametrize("size", [(640, 480), (100, 300), (1000, 200)])
def test_fit_image_size(fit, size):
    image = Image.new("RGB", size, "red")
    assert imageprep.fit_image(image, fit).size == (imageprep.WIDTH, imageprep.HEIGHT)


def test_contain_fills_background():
    image = Image.new("RGB", (100, 300), "red")
    fitted = imageprep.fit_image(image, "contain", "#00FF00")
    assert fitted.getpixel((0, 0)) == (0, 255, 0)
    assert fitted.getpixel((160, 120)) == (255, 0, 0)


def test_encode_png():
    image = Image.new("RGB", (imageprep.WIDTH, imageprep.HEIGHT), "blue")
    png = imageprep.encode_png(image)
    assert png.startswith(b"\x89PNG")
    assert Image.open(io.BytesIO(png)).size == (imageprep.WIDTH, imageprep.HEIGHT)


@pytest.mark.parametrize("fit", imageprep.FIT_MODES)
def test_fit_image_custom_size(fit):
    image = Image.new("RGB", (640, 480), "red")
    assert imageprep.fit_image(image, fit, size=(1280, 720)).size == (1280, 720)
