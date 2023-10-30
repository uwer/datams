from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required
from datams.db.views import (equipment_root, equipment_details, equipment_edit,
                             equipment_add, equipment_delete)


bp = Blueprint('equipment', __name__, url_prefix='/equipment')


@bp.route('/add', methods=('POST',))
@login_required
def add():
    equipment_add(request)
    return redirect(request.referrer)


@bp.route('/delete/<eid>', methods=('POST',))
@login_required
def delete(eid: int):
    equipment_delete(eid)
    return redirect(request.referrer)


@bp.route('/edit/<eid>', methods=('GET', 'POST'))
@login_required
def edit(eid: int):
    data = equipment_edit(eid, request)
    if request.method == 'GET' and data:
        return render_template('equipment/edit.html', data=data)
    elif request.method == 'POST':
        return redirect(url_for('equipment.edit', eid=eid))
    else:
        return redirect(url_for('equipment.root'))


@bp.route('/details/<eid>', methods=('GET',))
@login_required
def details(eid: int):
    data = equipment_details(eid)
    if not data:
        return redirect(url_for('equipment.root'))
    return render_template('equipment/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = equipment_root()
    return render_template('equipment/root.html', data=data)
