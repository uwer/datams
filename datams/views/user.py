from flask import (request, session, abort, redirect, flash, render_template, url_for,
                   Blueprint)
from flask_login import login_user, logout_user, login_required, current_user
from datams.db.auth import authenticate_user
from datams.utils import url_has_allowed_host_and_scheme

bp = Blueprint('user', __name__, url_prefix='/user')


@bp.route('/options', methods=('GET', ))
@login_required
def options():
    if current_user.role == 0:
        return render_template('user/admin_options.html')
    else:
        return render_template('user/normal_options.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        # validate user credentials
        user = authenticate_user(request)  # returns None or instance of User class
        if user is not None:
            # Log user in
            user_loaded = login_user(user)  # , remember=True)
            if user_loaded:
                # goto = session.get('next', url_for('organization.root'))
                # if not url_has_allowed_host_and_scheme(goto, request.host):
                #     return abort(400)
                # return redirect(goto)
                return redirect(url_for('organization.root'))
        flash('Incorrect email or password.  ')
    else:
        if current_user.is_authenticated:
            goto = session.get('next', url_for('organization.root'))
            if not url_has_allowed_host_and_scheme(goto, request.host):
                return abort(400)
            return redirect(goto)
    return render_template('user/login.html')


@bp.route("/logout", methods=('GET', ))
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect('/')
