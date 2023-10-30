from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import login_required
from datams.db.views import (contact_root, contact_details, contact_edit, contact_add,
                             contact_delete)

bp = Blueprint('contact', __name__, url_prefix='/contact')


@bp.route('/add', methods=('POST',))
@login_required
def add():
    contact_add(request)
    return redirect(request.referrer)


@bp.route('/delete/<cid>', methods=('POST',))
@login_required
def delete(cid: int):
    contact_delete(cid)
    return redirect(request.referrer)


@bp.route('/edit/<cid>', methods=('GET', 'POST'))
@login_required
def edit(cid: int):
    data = contact_edit(cid, request)
    if request.method == 'GET' and data:
        return render_template('contact/edit.html', data=data)
    elif request.method == 'POST':
        return redirect(url_for('contact.edit', cid=cid))
    else:
        return redirect(url_for('contact.root'))


@bp.route('/details/<cid>', methods=('GET',))
@login_required
def details(cid: int):
    data = contact_details(cid)
    if not data:
        return redirect(url_for('contact.root'))
    return render_template('contact/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = contact_root()
    return render_template('contact/root.html', data=data)
