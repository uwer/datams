from flask import (request, session, abort, redirect, flash, render_template, url_for,
                   Blueprint)
from flask_login import login_user, logout_user, login_required, current_user
from datams.db.auth import authenticate_user
from datams.utils import url_has_allowed_host_and_scheme
from datams.db.views import user_password_reset, admin_options

bp = Blueprint('user', __name__, url_prefix='/user')


@bp.route('/options', methods=('GET', ))
@login_required
def options():
    if current_user.role == 0:
        data = admin_options()
        data['users']
        return render_template('user/admin_options.html', data=data)
    else:
        return render_template('user/normal_options.html')


# TODO: Finish Implementing the following methods
@bp.route('/create', methods=('POST', ))
@login_required
def create():
    if current_user.role != 0:
        return redirect(request.referrer)
    return redirect(request.referrer)


@bp.route('/delete', methods=('POST', ))
@login_required
def delete():
    if current_user.role != 0:
        return redirect(request.referrer)
    return redirect(request.referrer)


@bp.route('/reset', methods=('POST', ))
@login_required
def reset():
    if current_user.role != 0:
        return redirect(request.referrer)
    return redirect(request.referrer)


@bp.route('/password_change/<required>', methods=('GET', 'POST'))
@login_required
def password_change(required: str):
    logout_only = False if required == 'False' else True
    # return render_template('user/password_reset.html')
    data = dict(username=current_user.username, logout_only=logout_only)
    if request.method == 'GET':
        return render_template('user/password_change.html', data=data)
    else:
        try:
            user_password_reset(request)
        except RuntimeError as error:
            flash(error.args[0])
            return render_template('user/password_change.html', data=data)
        flash('Password successfully updated. ')
        return redirect(url_for('user.options'))


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
    return redirect(url_for('user.login'))
