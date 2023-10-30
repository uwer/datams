from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required
from datams.db.views import (deployment_root, deployment_details, deployment_edit,
                             deployment_add, deployment_delete)


bp = Blueprint('deployment', __name__, url_prefix='/deployment')


@bp.route('/add', methods=('POST',))
@login_required
def add():
    deployment_add(request)
    return redirect(request.referrer)


@bp.route('/delete/<did>', methods=('POST',))
@login_required
def delete(did: int):
    deployment_delete(did)
    return redirect(request.referrer)


@bp.route('/edit/<did>', methods=('GET', 'POST'))
@login_required
def edit(did: int):
    data = deployment_edit(did, request)
    if request.method == 'GET' and data:
        return render_template('deployment/edit.html', data=data)
    elif request.method == 'POST':
        return redirect(url_for('deployment.edit', did=did))
    else:
        return redirect(url_for('deployment.root'))


@bp.route('/details/<did>', methods=('GET',))
@login_required
def details(did: int):
    data = deployment_details(did)
    if not data:
        return redirect(url_for('deployment.root'))
    return render_template('deployment/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = deployment_root()
    return render_template('deployment/root.html', data=data)
