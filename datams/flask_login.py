from datams.db.queries.select import select_user
from flask_login import LoginManager


def flask_login_init_app(app):
    # initialize the login manager and configure
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'user.login'
    login_manager.session_protection = "strong"  # TODO: Disable when running tests
    # login_manager.login_message = 'Please log in to access this page.  '
    # login_manager.login_message_category = 'info'
    # login_manager.refresh_view = "user.reauthenticate"
    # login_manager.needs_refresh_message = "For added security please re-authenticate"
    # login_manager.needs_refresh_message_category = "info"
    app.extensions['login_manager'] = login_manager

    # define how users are loaded
    @login_manager.user_loader
    def load_user(user_id):
        """
        It should return None (not raise an exception) if the ID is not valid. (In that
        case, the ID will manually be removed from the session and processing will
        continue.)
        """
        return select_user(view='load_user', user_id=user_id)

    # TODO: Implement the request_loader to allow login through api request.  This will
    #       be useful for email password reset and inviting new users via email so a url
    #       with api_key argument can be used to login.
    # @login_manager.request_loader
    # def load_user_from_request(request):
    #     # first, try to login using the api_key url arg
    #     api_key = request.args.get('api_key')
    #     if api_key:
    #         user = User.query.filter_by(api_key=api_key).first()
    #         if user:
    #             return user
    #
    #     # next, try to login using Basic Auth
    #     api_key = request.headers.get('Authorization')
    #     if api_key:
    #         api_key = api_key.replace('Basic ', '', 1)
    #         try:
    #             api_key = base64.b64decode(api_key)
    #         except TypeError:
    #             pass
    #         user = User.query.filter_by(api_key=api_key).first()
    #         if user:
    #             return user
    #
    #     # finally, return None if both methods did not login the user
    #     return None