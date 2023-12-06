from flask import Flask, redirect, url_for
import pandas as pd

from datams.utils import APP_CONFIG


def flask_init_app(name, test_config=None):
    # 1) create and configure the flask app instance
    app = Flask(name, instance_relative_config=True)

    # 2) configure the app
    app.config.from_mapping(APP_CONFIG)
    if test_config is not None: app.config.from_mapping(test_config)
    # app.config.from_prefixed_env()
    # app.url_map.strict_slashes = False  # TODO: Consider uncommenting

    # 3) add callbacks connected to application signals
    # @app.before_request
    # def before_request():
    #     # do something
    #    ...
    # @request_started.connect_via(app)
    # def when_request_started(_, **kwargs):
    #     # do something

    # 4) set globally available variables
    @app.context_processor
    def set_global_variables():
        return dict(
            google_api_key=app.config['GOOGLE_API_KEY'],
            pd=pd,
            # set the polling frequency to 4 times as often as the remove_stales
            # or every 10 second whichever is less
            polling_freq=min(
                round(app.config['DATA_FILES']['remove_stales_every'] * 250), 10000
            ),
        )

    # 5) add the root route
    @app.route('/', methods=('GET',))
    def root():
        """Navigating to home will always redirect to the login page.  """
        return redirect(url_for('user.login'))

    # 6) add all the other routes
    from datams.views import (
        organization, contact, equipment, deployment, file, mooring, user
    )
    app.register_blueprint(user.bp)
    app.register_blueprint(organization.bp)
    app.register_blueprint(contact.bp)
    app.register_blueprint(equipment.bp)
    app.register_blueprint(deployment.bp)
    app.register_blueprint(mooring.bp)
    app.register_blueprint(file.bp)

    return app
