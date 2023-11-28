import datetime as dt
import os

from flask import Flask, redirect, url_for, request_started, session, request
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
    @app.before_request
    def set_session_identity():
        if 'identity' not in session:
            session['identity'] = (f"{dt.datetime.now().timestamp():10.6f}"
                                   .replace('.', ''))

    @app.before_request
    def clear_partial_pending():
        if request.path != '/file/upload':
            identity = session.get('identity', None)
            if identity is not None:
                pending_dir = f"{app.config['DATA_FILES']['upload_directory']}/pending"
                to_remove = [f"{pending_dir}/{f}" for f in os.listdir(pending_dir)
                             if f.startswith(f".temp.{identity}.")]
                for f in to_remove:
                    os.remove(f)

    # 4) set globally available variables for templates
    @app.context_processor
    def set_global_template_variables():
        return dict(
            google_api_key=app.config['GOOGLE_API_KEY'],
            pd=pd
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
