from flask import Blueprint, render_template, url_for, redirect, request
from flask_login import login_required
from datams.db.views import (mooring_root, mooring_details, mooring_edit, mooring_add,
                             mooring_delete)


bp = Blueprint('mooring', __name__, url_prefix='/mooring')


@bp.route('/add', methods=('POST',))
@login_required
def add():
    mooring_add(request)
    return redirect(request.referrer)


@bp.route('/delete/<mid>', methods=('POST',))
@login_required
def delete(mid: int):
    mooring_delete(mid)
    return redirect(request.referrer)


@bp.route('/edit/<mid>', methods=('GET', 'POST'))
@login_required
def edit(mid: int):
    data = mooring_edit(mid, request)
    if request.method == 'GET' and data:
        return render_template('mooring/edit.html', data=data)
    elif request.method == 'POST':
        return redirect(url_for('mooring.edit', mid=mid))
    else:
        return redirect(url_for('mooring.root'))


@bp.route('/details/<mid>', methods=('GET',))
@login_required
def details(mid: int):
    data = mooring_details(mid)
    if not data:
        return redirect(url_for('mooring.root'))
    return render_template('mooring/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = mooring_root()
    return render_template('mooring/root.html', data=data)
