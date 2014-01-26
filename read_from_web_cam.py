import requests
import cv2
import numpy as np
from StringIO import StringIO

META_DATA_LENGTH = 110
IP_ADDRESS = "10.10.100.100"
PORT = 80

# authentication requirements have been removed from the camera
CAMERA_URL = "http://%s:%s/mjpeg.cgi" % (IP_ADDRESS, PORT)

frame_buffer = StringIO()


class StreamState(object):
    SEEKING_META_DATA = 0
    GETTING_ALL_META_DATA = 1
    READING_IMAGE = 2


def image_yielder(response_stream):
    meta_data_seeker = StringIO()
    current_state = StreamState.SEEKING_META_DATA
    prev_char = " "
    for line in response_stream.iter_content(chunk_size=2048, decode_unicode=False):
        if current_state == StreamState.SEEKING_META_DATA:
            meta_data_seeker.write(line)
            if meta_data_seeker.len >= META_DATA_LENGTH:
                string_to_examine = meta_data_seeker.getvalue()
                if "Content-length" in string_to_examine:
                    starting_index = string_to_examine.index("Content-length")
                    meta_data_seeker.seek(starting_index)
                    initial_bytes = meta_data_seeker.read()
                    new_buffer_for_image_reading = StringIO()
                    new_buffer_for_image_reading.write(initial_bytes)
                    current_state = StreamState.GETTING_ALL_META_DATA
                    meta_data_seeker = None
                else:
                    meta_data_seeker = StringIO()
        elif current_state == StreamState.GETTING_ALL_META_DATA:
            new_buffer_for_image_reading.write(line)
            if new_buffer_for_image_reading.len >= META_DATA_LENGTH:
                current_state = StreamState.READING_IMAGE
                content_length, image_buffer = _get_content_length_and_fresh_image_buffer(new_buffer_for_image_reading)
                new_buffer_for_image_reading = None
        elif current_state == StreamState.READING_IMAGE:
            for byte in line:
                current_char = byte.encode("hex")
                if current_char == "d9" and prev_char == "ff":
                    image_buffer.write(byte)
                    image_buffer.seek(0)
                    raw_bytes = bytearray(image_buffer.read())
                    img_array = cv2.imdecode(np.asarray(raw_bytes), cv2.CV_LOAD_IMAGE_UNCHANGED)
                    yield img_array
                    meta_data_seeker = StringIO()
                    current_state = StreamState.SEEKING_META_DATA
                    image_buffer = None
                else:
                    if current_state == StreamState.SEEKING_META_DATA:
                        meta_data_seeker.write(byte)
                    else:
                        image_buffer.write(byte)
                prev_char = current_char


def _get_content_length_and_fresh_image_buffer(buffer):
    meta_data = buffer.getvalue()
    index_start = meta_data.index("Content-length: ") + len("Content-length: ")
    index_end = meta_data.index("Date")
    content_length = int(meta_data[index_start: index_end])
    end_meta_data_index = meta_data.index("image/jpeg") + len("image/jpeg")
    buffer.seek(end_meta_data_index)
    next_array = bytearray(buffer.read(50))  # 50 is an arbitrary "long enough" number
    offset = 0
    # this is pretty hacky.  Just seeking the first instance of 255 which would
    # indicate the start of a jpeg file
    for byte in next_array:
        if byte == 255:
            break
        offset += 1
    buffer.seek(end_meta_data_index + offset)
    new_buffer = StringIO()
    new_buffer.write(buffer.read())
    return content_length, new_buffer


def init_connection():
    session = requests.Session()
    request = requests.Request("GET", CAMERA_URL).prepare()
    response_stream = session.send(request, stream=True)
    return response_stream


def get_cv_img_from_ip_cam():
    response_stream = init_connection()
    for cv_img_array in image_yielder(response_stream):
        yield cv_img_array


if __name__ == "__main__":
    cv2.namedWindow("test", 0)
    for img_array in get_cv_img_from_ip_cam():
        cv2.imshow("test", img_array)
        cv2.waitKey(1)
