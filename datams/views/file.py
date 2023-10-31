import os
import random
import string
from flask import (Blueprint, render_template, request, redirect, url_for, send_file,
                   jsonify, make_response, session)
from flask_login import login_required
from datams.db.views import (file_root, file_details, file_edit, file_download,
                             file_add, file_delete)
from datams.db.datatables import request_dfiles
from datams.utils import PENDING_UPLOAD_FOLDER
from werkzeug.utils import secure_filename


import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


bp = Blueprint('file', __name__, url_prefix='/file')


# TODO: look into using celery with parallel chunk downloading to speed things up
@bp.route("/upload", methods=('POST',))
@login_required
def upload():
    if 'identity' not in session:
        session['identity'] = ''.join(
            random.choices(string.ascii_letters + string.digits, k=16)
        )

    file = request.files['file']
    save_path = os.path.join(
        PENDING_UPLOAD_FOLDER, f"{session['identity']}_{secure_filename(file.filename)}"
    )
    current_chunk = int(request.form['dzchunkindex'])

    # TODO: Use multiprocessing to speed things up and start assembling the file in
    #       memory
    # If the file already exists it's ok if we are appending to it,
    # but not if it's new file that would overwrite the existing one
    if os.path.exists(save_path) and current_chunk == 0:
        # 400 and 500s will tell dropzone that an error occurred and show an error
        return make_response(('File already exists', 400))
    try:
        with open(save_path, 'ab') as f:
            f.seek(int(request.form['dzchunkbyteoffset']))
            f.write(file.stream.read())
    except OSError:
        # log.exception will include the traceback so we can see what's wrong
        log.exception('Could not write to file')
        return make_response(("Not sure why,"
                              " but we couldn't write the file to disk", 500))
    total_chunks = int(request.form['dztotalchunkcount'])
    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form['dztotalfilesize']):
            log.error(f"File {file.filename} was completed, "
                      f"but has a size mismatch."
                      f"Was {os.path.getsize(save_path)} but we"
                      f" expected {request.form['dztotalfilesize']} ")
            return make_response(('Size mismatch', 500))
        else:
            log.info(f'File {file.filename} has been uploaded successfully')
    else:
        log.debug(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')
    return make_response(("Chunk upload successful", 200))


@bp.route("/download/<fid>&<dl>", methods=('GET',))
@login_required
def download(fid, dl):
    dl = True if str(dl).lower() == 'true' else False
    data = file_download(fid)
    if not data:
        return redirect(request.referrer)
    try:
        path, filename = tuple(data['file'])
        return send_file(os.path.realpath(path), as_attachment=dl,
                         download_name=filename)
    except Exception as e:
        return str(path)


@bp.route("/datatable_request", methods=('GET',))
@login_required
def datatable_request():
    return jsonify(request_dfiles(request))


@bp.route('/add', methods=('POST',))
@login_required
def add():
    file_add(request, session)
    return redirect(request.referrer)


@bp.route('/delete/<fid>', methods=('POST',))
@login_required
def delete(fid: int):
    file_delete(fid)
    return redirect(request.referrer)


@bp.route('/edit/<fid>', methods=('GET', 'POST'))
@login_required
def edit(fid: int):
    data = file_edit(fid, request)
    if request.method == 'GET' and data:
        return render_template('file/edit.html', data=data)
    elif request.method == 'POST':
        return redirect(url_for('file.edit', fid=fid))
    else:
        return redirect(url_for('file.root'))


@bp.route('/details/<fid>', methods=('GET',))
@login_required
def details(fid: int):
    data = file_details(fid)
    if not data:
        return redirect(request.referrer)
    return render_template('file/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    data = file_root()
    return render_template('file/root.html', data=data)