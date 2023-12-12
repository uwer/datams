from flask import Flask, redirect, url_for, render_template
import pandas as pd

from datams.utils import APP_CONFIG
from datams.flask_login import check_password_expiry


def flask_init_app(name, test_config=None):
    # 1) create and configure the flask app instance
    app = Flask(name, instance_relative_config=True)

    # 2) configure the app
    app.config.from_mapping(APP_CONFIG)
    if test_config is not None: app.config.from_mapping(test_config)
    # app.config.from_prefixed_env()
    # app.url_map.strict_slashes = False  # TODO: Consider uncommenting

    # 3) register the command-line scripts
    from datams.cli import (
        wipe_db_command, init_db_command, resolve_files_command, create_user_command,
        delete_user_command
    )
    app.cli.add_command(wipe_db_command)  # register the wipe-db command
    app.cli.add_command(init_db_command)  # register the init-db command
    app.cli.add_command(resolve_files_command)  # ...
    app.cli.add_command(create_user_command)
    app.cli.add_command(delete_user_command)

    # 4) add callbacks connected to application signals
    @app.before_request
    def is_password_expired():
        return check_password_expiry()
        # do something
    #    ...
    # @request_started.connect_via(app)
    # def when_request_started(_, **kwargs):
    #     # do something

    # 5) set globally available variables
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

    # 6) add the root route
    @app.route('/', methods=('GET',))
    def root():
        """Navigating to home will always redirect to the login page.  """
        return redirect(url_for('organization.root'))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    # 7) register the blueprints containing all the other routes
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
