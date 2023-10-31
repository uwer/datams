from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required
from datams.db.views import (organization_root, organization_details, organization_edit,
                             organization_add, organization_delete)
from datams.utils import APP_CONFIG

bp = Blueprint('organization', __name__, url_prefix='/organization')


@bp.route('/add', methods=('POST',))
@login_required
def add():
    organization_add(request)
    return redirect(request.referrer)


@bp.route('/delete/<oid>', methods=('POST',))
@login_required
def delete(oid: int):
    organization_delete(oid)
    return redirect(request.referrer)


@bp.route('/edit/<oid>', methods=('GET', 'POST'))
@login_required
def edit(oid: int):
    data = organization_edit(oid, request)
    if request.method == 'GET' and data:
        return render_template('organization/edit.html', data=data)
    elif request == 'POST':
        return redirect(url_for('organization.edit', oid=oid))
    else:
        return redirect(url_for('organization.root'))


@bp.route('/details/<oid>', methods=('GET',))
@login_required
def details(oid: int):
    data = organization_details(oid)
    if not data:
        return redirect(url_for('organization.root'))
    return render_template('organization/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = organization_root()
    return render_template('organization/root.html', data=data)
