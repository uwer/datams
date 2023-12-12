import os
import base64
import shutil
from urllib.parse import urlparse
import unicodedata

import numpy as np
import cv2
from typing import List
from math import trunc
import datetime as dt
from xml.etree import ElementTree
import seaborn as sns
import yaml

from flask import current_app

def expand_environmental_variables(d):
    if issubclass(type(d), str):
        return os.path.expandvars(d)
    elif issubclass(type(d), dict):
        d2 = dict()
        for k, v in d.items():
            d2[k] = expand_environmental_variables(v)
        return d2
    else:
        return d


DATAMS_CONFIG = "DATAMS_CONFIG"

rootdir = os.path.dirname(os.path.realpath(__file__))

conf_file = os.getenv(DATAMS_CONFIG,os.path.join(rootdir, "config.yml"))

# with open(conf_file, "r") as conf_fp:
#     config = yaml.safe_load(conf_fp)
# with open(os.path.join(rootdir, "config.yml"), "r") as conf_fp:

with open(conf_file, "r") as conf_fp:
    config = yaml.safe_load(conf_fp)
    config = expand_environmental_variables(config)

# TODO: Enforce these for certain things such as deployment, mooring, organization, user
#       names.
ALLOWED_CHARACTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                      'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                      'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                      'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
                      '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '_', '-']

APP_CONFIG = config['app']
MAP_CONFIG = config['map']
MENU_CONFIG = config['menu']

UPLOADS_DIRECTORY = APP_CONFIG['DATA_FILES']['upload_directory']
ALLOWED_UPLOAD_EXTENSIONS = APP_CONFIG['DATA_FILES']['allowed_extensions']

DISCOVERY_DIRECTORY = os.path.realpath(APP_CONFIG['DATA_FILES']['discovery_directory'])
PENDING_DIRECTORY = os.path.realpath(f"{UPLOADS_DIRECTORY}/pending/")
PROCESSED_DIRECTORY = os.path.realpath(f"{UPLOADS_DIRECTORY}/processed/")
REMOVE_STALES_EVERY = APP_CONFIG['DATA_FILES']['remove_stales_every']  # in seconds

utc_offsets = sorted(
    list(range(-12, 15)) +  # regular offsets
    [-9.5, -3.5, 3.5, 4.5, 5.5, 5.75, 6.5, 8.75, 9.5, 10.5, 12.75]  # other offsets
)
TIMEZONES = dict(
    **{
        f"UTC{str(trunc(i)).zfill(3)}:{str(int(round((abs(i) % 1) * 60))).zfill(2)}": i
        for i in utc_offsets
        if i < 0
    },
    **{
        f"UTC+{str(trunc(i)).zfill(2)}:{str(int(round((i % 1) * 60))).zfill(2)}": i
        for i in utc_offsets
        if i >= 0
    }
)
TIMEZONES_R = {str(float(v)): k for k, v in TIMEZONES.items()}


def update_and_append_to_checkins(checkins, value):
    upload_id, timestamp = value
    # remove valid checkins with same upload_id as the new value
    checkins = [(uid, ts) for uid, ts in get_valid_checkins(checkins)
                if uid != upload_id]
    checkins.append(value)  # append the new value
    return checkins


def get_valid_checkins(checkins):
    # return checkins that haven't yet expired
    now = dt.datetime.now().timestamp()
    checkins = [a for a in checkins if (now - a[1]) < REMOVE_STALES_EVERY]
    return checkins


def remove_stale_files(valid_uids):
    temp_files = [f for f in os.listdir(PENDING_DIRECTORY)
                  if (os.path.isfile(f"{PENDING_DIRECTORY}/{f}") and
                      f.startswith('.temp'))]
    to_remove = [f"{PENDING_DIRECTORY}/{f}" for f in temp_files
                 if '.'.join(f[6:].split('.')[:2]) not in valid_uids]
    for f in to_remove:
        if os.path.isfile(f):
            os.remove(f)


def current_timestamp():
    return int(round(dt.datetime.now().timestamp()))


def allowed_upload(file):
    # TODO: Implement this using regular expression
    return '.' in file and file.lower().split('.')[-1] in ALLOWED_UPLOAD_EXTENSIONS


def datetimestr_to_timestamp(datetime_str: str):
    if datetime_str == '':
        return None
    elif len(datetime_str) == 19:
        retval = int(round(
            dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S").timestamp()
        ))
    elif len(datetime_str) == 16:
        retval = int(round(
            dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M").timestamp()
        ))
    else:
        return None
    return retval


def save_fileobj(file_obj, path):
    if file_obj is not None and file_obj.filename != '':
        file_obj.save(path)


# def resolve_filepath(file_obj):
#     # TODO: Check if the file is the allowed extension
#     if file_obj is None or file_obj.filename == '':
#         return None
#     else:
#         filename = secure_filename(file_obj.filename)
#         return os.path.join(SUBMITTED_UPLOAD_FOLDER, filename)

def move_pending_files(session):
    identity = session['identity']
    for f in os.listdir(PENDING_DIRECTORY):
        if f.startswith(identity):
            shutil.move(
                os.path.join(PENDING_DIRECTORY, f),
                os.path.join(PROCESSED_DIRECTORY, f[17:])
            )


# def parse_dfiles(dfiles: str) -> List[str]:
#     log.debug(dfiles)


def fileobj_to_jpgbytes(file_obj):
    if file_obj is None or file_obj.filename == '':
        return None
    else:
        byte_string = file_obj.stream.read()
        img_np = np.frombuffer(byte_string, dtype=np.uint8)
        img1 = cv2.imdecode(img_np, flags=1)
        img2 = cv2.resize(img1, (260, 260))
        img3, buffer = cv2.imencode('.jpg', img2)
        img = buffer.tobytes()
        return img


def jpgbytes_to_base64(buffer):
    return base64.b64encode(buffer).decode('utf-8')


def svg_d_value(file: str) -> str:
    """
    param: file - `str` representing a svg image file

    return: `str` - the path.d value from a svg file
    """
    tree = ElementTree.parse(file)
    root = tree.getroot()
    return [child for child in root][0].attrib['d']


def get_colors(number: int) -> List[str]:
    """
    Given the `number` parameter which is an integer this method generates a list of hex
    strings representing colors from the seaborn hls color palette of length `number`.
    ex. ['#aabbee', '#000000']
    """
    def seaborn_to_hex(c):
        return '#' + ''.join([hex(min(int(round(v * 255)), 255))[2:] for v in c])
    return [seaborn_to_hex(c) for c in sns.color_palette("hls", number)]


def _url_has_allowed_host_and_scheme(url, allowed_hosts, require_https=False):
    # Chrome considers any URL with more than two slashes to be absolute, but
    # urlparse is not so flexible. Treat any url with three slashes as unsafe.
    if url.startswith('///'):
        return False
    try:
        url_info = urlparse(url)
    except ValueError:  # e.g. invalid IPv6 addresses
        return False
    # Forbid URLs like http:///example.com - with a scheme, but without a hostname.
    # In that URL, example.com is not the hostname but, a path component. However,
    # Chrome will still consider example.com to be the hostname, so we must not
    # allow this syntax.
    if not url_info.netloc and url_info.scheme:
        return False
    # Forbid URLs that start with control characters. Some browsers (like
    # Chrome) ignore quite a few control characters at the start of a
    # URL and might consider the URL as scheme relative.
    if unicodedata.category(url[0])[0] == 'C':
        return False
    scheme = url_info.scheme
    # Consider URLs without a scheme (e.g. //example.com/p) to be http.
    if not url_info.scheme and url_info.netloc:
        scheme = 'http'
    valid_schemes = ['https'] if require_https else ['http', 'https']
    return ((not url_info.netloc or url_info.netloc in allowed_hosts) and
            (not scheme or scheme in valid_schemes))


def url_has_allowed_host_and_scheme(url, allowed_hosts, require_https=False):
    """
    Return ``True`` if the url uses an allowed host and a safe scheme.

    Always return ``False`` on an empty url.

    If ``require_https`` is ``True``, only 'https' will be considered a valid
    scheme, as opposed to 'http' and 'https' with the default, ``False``.

    Note: "True" doesn't entail that a URL is "safe". It may still be e.g.
    quoted incorrectly. Ensure to also use django.utils.encoding.iri_to_uri()
    on the path component of untrusted URLs.
    """
    if url is not None:
        url = url.strip()
    if not url:
        return False
    if allowed_hosts is None:
        allowed_hosts = set()
    elif isinstance(allowed_hosts, str):
        allowed_hosts = {allowed_hosts}
    # Chrome treats \ completely as / in paths but it could be part of some
    # basic auth credentials so we need to check both URLs.
    return (
        _url_has_allowed_host_and_scheme(url, allowed_hosts, require_https=require_https) and
        _url_has_allowed_host_and_scheme(url.replace('\\', '/'), allowed_hosts, require_https=require_https)
    )

# TODO: Implement something like this to decorate views and prevent unauthorized users
#       from doing things they are not allowed
# def login_required(func):
#     """
#     If you decorate a view with this, it will ensure that the current user is
#     logged in and authenticated before calling the actual view. (If they are
#     not, it calls the :attr:`LoginManager.unauthorized` callback.) For
#     example::
#
#         @app.route('/post')
#         @login_required
#         def post():
#             pass
#
#     If there are only certain times you need to require that your user is
#     logged in, you can do so with::
#
#         if not current_user.is_authenticated:
#             return current_app.login_manager.unauthorized()
#
#     ...which is essentially the code that this function adds to your views.
#
#     It can be convenient to globally turn off authentication when unit testing.
#     To enable this, if the application configuration variable `LOGIN_DISABLED`
#     is set to `True`, this decorator will be ignored.
#
#     .. Note ::
#
#         Per `W3 guidelines for CORS preflight requests
#         <http://www.w3.org/TR/cors/#cross-origin-request-with-preflight-0>`_,
#         HTTP ``OPTIONS`` requests are exempt from login checks.
#
#     :param func: The view function to decorate.
#     :type func: function
#     """
#
#     @wraps(func)
#     def decorated_view(*args, **kwargs):
#         if request.method in EXEMPT_METHODS or current_app.config.get("LOGIN_DISABLED"):
#             pass
#         elif not current_user.is_authenticated:
#             return current_app.login_manager.unauthorized()
#
#         # flask 1.x compatibility
#         # current_app.ensure_sync is only available in Flask >= 2.0
#         if callable(getattr(current_app, "ensure_sync", None)):
#             return current_app.ensure_sync(func)(*args, **kwargs)
#         return func(*args, **kwargs)
#
#     return decorated_view