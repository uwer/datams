import flask
from werkzeug.security import check_password_hash

from datams.db.requests import parse_request
from datams.db.queries.select import select_user


def authenticate_user(request: flask.Request):
    kwargs = parse_request(request, 'User', rtype='auth')
    user = select_user(view='authenticate_user', **kwargs)
    if user is not None and check_password_hash(user.password, kwargs['user_password']):
        return user
    return None
