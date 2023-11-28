import os
from flask import (Blueprint, render_template, request, redirect, url_for, send_file,
                   jsonify, make_response, session)
from flask_login import login_required
from datams.db.views import (file_root, file_details, file_edit, file_download,
                             file_add, file_delete, file_pending)
from datams.db.datatables import request_files
from datams.celery import load_pending_files
from datams.utils import PENDING_DIRECTORY
from werkzeug.utils import secure_filename

from datams.redis import get_pending_files, get_discovered_files


import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


bp = Blueprint('file', __name__, url_prefix='/file')


def is_pending(file):
    df = get_pending_files()
    df['file'] = df['file'].apply(lambda x: os.path.basename(x))
    if file in list(df['file']):
        p = True
    else:
        p = any(
            [True for f in df['file']
             if f.endswith(file) and
             f.startswith('.temp') and
             len(f) == (len(file) + 23)]  # 23 is length of prepended portion of
                                          # partially downloaded files
        )
    return p


# @bp.route("/resolve_filename/<file>", methods=('GET',))
# @login_required
def resolve_filename(file):
    i = 0
    f = secure_filename(file)
    while is_pending(f):
        f = secure_filename(file)
        fl = f.split('.')
        f = secure_filename(
            f"{'.'.join(fl[:-1])}_{i}.{fl[-1]}" if len(fl) > 1 else f"{f}_{i}"
        )
        i += 1
    return f


# TODO: look into using celery with parallel chunk downloading to speed things up
@bp.route("/upload", methods=('POST',))
@login_required
def upload():
    file = request.files['file']
    save_path = os.path.join(
        PENDING_DIRECTORY, f".temp.{session['identity']}.{secure_filename(file.filename)}"
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
            parent, _ = os.path.split(save_path)
            filename = resolve_filename(file.filename)
            load_pending_files(PENDING_DIRECTORY)
            os.rename(save_path, f"{parent}/{filename}")
            log.info(f'File {filename} has been uploaded successfully')
    else:
        log.debug(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')
    return make_response(("Chunk upload successful", 200))


@bp.route("/download/<fid>&<dl>", methods=('GET',))
@login_required
def download(fid, dl):
    dl = True if dl == 'True' else False
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
    return jsonify(request_files(request))


@bp.route('/add', methods=('POST',))
@login_required
def add():
    # TODO: Check that the files have finished uploading
    #       - do this by putting temp in name until it is completed.
    #       - if session, temp in name remove the file

    #       this can be done via checking all the files that
    file_add(request, session)
    return redirect(request.referrer)


@bp.route('/pending', methods=('GET', 'POST'))
@login_required
def pending():
    # data = file_pending()
    data = dict(files=get_discovered_files())
    return render_template('file/pending.html', data=data)


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
