import os
import datetime as dt
from flask import (Blueprint, render_template, request, redirect, url_for, send_file,
                   jsonify, make_response, session)
from flask_login import login_required, current_user
from datams.db.views import (file_root, file_details, file_edit, file_download,
                             file_delete)  # file_add, file_pending
from datams.db.datatables import processed_files, discovered_files
# from datams.celery import load_pending_files
from datams.utils import PENDING_DIRECTORY
from werkzeug.utils import secure_filename

# from datams.redis import get_pending_files, get_discovered_files
import logging

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


bp = Blueprint('file', __name__, url_prefix='/file')


# def _is_pending():
#     # TODO: Does the following need to be a background process or can we just do it
#     #       adhoc
#     df = pending_files
#     df['file'] = df['file'].apply(lambda x: os.path.basename(x))
#     if f in list(df['file']):
#         p = True
#     else:
#         p = any(
#             [True for i in df['file']
#              if i.endswith(f) and
#              i.startswith('.temp') and
#              len(f) == (len(f) + 32)]  # 32 is length of prepended portion of
#             # partially downloaded files
#         )
#     return p


def exists(filename, directory):
    return filename in os.listdir(directory)


def resolve_filename(filename, directory):
    i = 0
    new_filename = filename
    while exists(new_filename, directory):
        fl = filename.split('.')
        new_filename = secure_filename(
            f"{'.'.join(fl[:-1])}_{i}.{fl[-1]}" if len(fl) > 1 else f"{filename}_{i}"
        )
        i += 1
    return f"{directory}/{new_filename}"


# TODO: look into using celery with parallel chunk downloading to speed things up
# TODO: Use multiprocessing to speed things up and start assembling the file in
#       memory
@bp.route("/upload", methods=('POST',))
@login_required
def upload():
    file = request.files['file']
    # save_path = os.path.join(
    #     PENDING_DIRECTORY, f".temp.{session['identity']}.{secure_filename(file.filename)}"
    # )
    save_path = os.path.join(
        PENDING_DIRECTORY,
        secure_filename(file.filename)
    )
    log.debug(save_path)
    current_chunk = int(request.form['dzchunkindex'])

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
            # TODO: Remove the renaming into the submit button
            # parent, _ = os.path.split(save_path)
            # filename = resolve_filename(file.filename)
            # load_pending_files(PENDING_DIRECTORY)
            # os.rename(save_path, f"{parent}/{filename}")
            filename = os.path.basename(save_path)
            log.info(f'File {filename} has been uploaded successfully')
    else:
        log.debug(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')
    return make_response(("Chunk upload successful", 200))


@bp.route('/submit', methods=('POST',))
@login_required
def submit():
    uploads_id = request.form['uploads_id']
    pending_files = [f"{PENDING_DIRECTORY}/{i}" for i in os.listdir(PENDING_DIRECTORY)
                     if i.startswith(f"temp.{uploads_id}.")]
    for f in pending_files:
        parent, filename = os.path.split(f)
        f_new = resolve_filename(filename[32:], parent)
        os.rename(f, f_new)
    return redirect(request.referrer)


@bp.route('/cancel', methods=('POST',))
@login_required
def cancel():
    # TODO: Get this working in add.html modal
    uploads_id = request.form['uploads_id']
    pending_files = [f"{PENDING_DIRECTORY}/{i}" for i in os.listdir(PENDING_DIRECTORY)
                     if i.startswith(f"temp.{uploads_id}.")]
    for f in pending_files:
        os.remove(f)
    return redirect(request.referrer)


@bp.route('/process', methods=('POST',))
@login_required
def process():
    # TODO: Implement this
    # this will cancel and remove all un-submitted uploads
    return redirect(request.referrer)


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
    # TODO: Add a unique identifier (i.e.) user and timestamp to be passed to the
    #       template so this can be used to remove cancelled files etc.
    #       (do this instead of using session[identity] this will solve issues of using
    #       multiple tabs)
    data = file_root()
    data['uploads_id'] = f"{current_user.id}".zfill(10) + data['uploads_id']
    return render_template('file/root.html', data=data)


@bp.route("/processed_datatable", methods=('GET',))
@login_required
def processed_datatable():
    return jsonify(processed_files(request))


@bp.route("/discovered_datatable", methods=('GET',))
@login_required
def discovered_datatable():
    return jsonify(discovered_files(request))



# -------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------
# TODO: Consider removing the following

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

# @bp.route("/pending", methods=('GET', 'POST'))
# @login_required
# def pending():
#     # TODO: Add the pending files in here too
#     data = dict(files=get_discovered_files())
#     return render_template('file/pending.html', data=data)

# TODO: Do we need these?
# @bp.route("/pending_datatable", methods=('GET',))
# @login_required
# def pending_datatable():
#     return jsonify(pending_files(request))
#
#
# @bp.route("/test_datatable", methods=('GET', 'POST'))
# @login_required
# def test_datatable():
#     return jsonify(test_files(request))