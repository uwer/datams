import os
import pandas as pd
import datetime as dt
from flask import (Blueprint, render_template, request, redirect, send_file, url_for,
                   jsonify, make_response)
from flask_login import login_required, current_user
from datams.celery import (update_task, compute_and_set_task, task_complete,
                           update_vkey, set_working)
from datams.redis import get_value
from datams.db.views import file_root, file_details
from datams.db.requests import parse_request
from datams.db.datatables import fetch
from datams.db.utils import (resolve_filename, resolve_directory,
                             check_directory_fullness)
from datams.utils import PENDING_DIRECTORY, PROCESSED_DIRECTORY
from werkzeug.utils import secure_filename
from datams.db.queries.insert import insert_files
from datams.db.queries.update import update_files
import logging

from sqlalchemy import select, insert
from sqlalchemy import delete as sdelete
from datams.db.core import query_all, query_df
from datams.db.tables import File, DeletedFile

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# CHUNK_SIZE = 1000000  # ~1MB


bp = Blueprint('file', __name__, url_prefix='/file')

# TODO: Put the query code from methods process, delete into the appropriate files
# TODO: look into using celery with parallel chunk downloading to speed things up
# TODO: Use multiprocessing to speed things up and start assembling the file in
#       memory
@bp.route("/upload", methods=('POST',))
@login_required
def upload():
    file = request.files['file']
    save_path = os.path.join(
        PENDING_DIRECTORY,
        f".{secure_filename(file.filename)}"
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
        return make_response(("Not sure why, but we couldn't write the file to disk",
                              500))
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
            filename = os.path.basename(save_path)
            log.info(f'File {filename} has been uploaded successfully')
    else:
        log.debug(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')
    return make_response(("Chunk upload successful", 200))


@bp.route('/checkin', methods=('POST',))
@login_required
def checkin():
    update_task.delay('checkins',
                      (request.form['uploads_id'], dt.datetime.now().timestamp()))
    return make_response(("Successful check-in", 200))


@bp.route('/submit', methods=('POST',))
@login_required
def submit():
    # Check that the user portion of the uploads_id matches the current user
    if current_user.username == request.form['uploads_id'].split('.')[0]:
        uploads_id = request.form['uploads_id']
        pending_files = [i for i in os.listdir(PENDING_DIRECTORY)
                         if i.startswith(f".temp.{uploads_id}.")]
        for f in pending_files:
            cdir, cdir_idx, cdir_count = resolve_directory(PENDING_DIRECTORY)
            f_new = resolve_filename(f[6:], cdir)
            os.rename(f"{PENDING_DIRECTORY}/{f}", f"{cdir}/{f_new}")
        set_working('pending_files')
        compute_and_set_task.delay('pending_files')
    return redirect(f"{url_for('file.root')}?activetab=nav-pending-uploads")


@bp.route('/cancel', methods=('POST',))
@login_required
def cancel():
    # Check that the user portion of the uploads_id matches the current user
    if current_user.username == request.form['uploads_id'].split('.')[0]:
        uploads_id = request.form['uploads_id']
        pending_files = [f"{PENDING_DIRECTORY}/{i}"
                         for i in os.listdir(PENDING_DIRECTORY)
                         if i.startswith(f".temp.{uploads_id}.")]
        for f in pending_files:
            os.remove(f)
    return redirect(request.referrer)


@bp.route('/delete', methods=('POST',))
@login_required
def delete():
    values = parse_request(request, table='File', rtype='delete')
    ftype, uploads_id = values.pop('ftype'), values.pop('uploads_id')
    active_tab = 'nav-processed'
    if ftype == 'processed_files':
        indexes = values.pop('indexes')
        # get all the indexes from the table
        df = query_df(select(
            File.id, File.organization_id, File.deployment_id,
            File.mooring_equipment_id, File.path, File.name, File.description,
            File.uploaded, File.comments
        ).where(File.id.in_(indexes)))
        df['ftype'] = 'processed_file'
        df['deleted'] = int(round(dt.datetime.now().timestamp()))
        df = df.rename(columns={'id': 'original_id'})
        values = [v for v in df.transpose().to_dict().values()]
        # insert these into deleted files and remove these from the File table
        query_all([insert(DeletedFile).values(**v) for v in values] +
                  [sdelete(File).where(File.id.in_(indexes))])
        set_working('processed_files')
        set_working('deleted_files')
        compute_and_set_task.delay('processed_files')
        compute_and_set_task.delay('deleted_files')

    elif ftype == 'pending_files':
        active_tab = 'nav-pending-uploads'
        indexes = values.pop('indexes')
        # get all the indexes from the table
        df = get_value(f"vkey_{uploads_id}_pending_files").drop(columns=['uploaded_by'])
        df = df.loc[df['id'].isin(indexes), :]
        df['ftype'] = 'pending_file'
        df['deleted'] = int(round(dt.datetime.now().timestamp()))
        df['uploaded'] = df['uploaded'].apply(
            lambda x: x if x is None
            else int(round(dt.datetime.strptime(x, "%Y-%m-%d %H:%M:%S").timestamp()))
        )
        df = df.rename(columns={'id': 'original_id', 'filepath': 'path',
                                'filename': 'name'})
        values = [v for v in df.transpose().to_dict().values()]
        # insert these into deleted files and remove these from the File table
        query_all([insert(DeletedFile).values(**v) for v in values])
        set_working('pending_files')
        set_working('deleted_files')
        compute_and_set_task.delay('pending_files')
        compute_and_set_task.delay('deleted_files')

    return redirect(f"{url_for('file.root')}?activetab={active_tab}")


@bp.route('/restore', methods=('POST',))
@login_required
def restore():
    values = parse_request(request, table='File', rtype='restore')
    uploads_id, indexes = values.pop('uploads_id'), values.pop('indexes')
    # df = get_value(f"vkey_{uploads_id}_deleted_files")
    stmt = select(DeletedFile.id, DeletedFile.original_id, DeletedFile.organization_id,
                  DeletedFile.deployment_id, DeletedFile.mooring_equipment_id,
                  DeletedFile.path, DeletedFile.name, DeletedFile.description,
                  DeletedFile.uploaded, DeletedFile.comments, DeletedFile.ftype)
    df = query_df(stmt)
    df = (
        df.loc[df['id'].isin(indexes), :]
          .drop(columns=['id'])
          .rename(columns={'original_id': 'id'})
    )
    df = df.loc[df['ftype'] == 'processed_file', :].drop(columns=['ftype'])
    refresh_processed = df.shape[0] != 0
    # values = [v for v in df.transpose().to_dict().values()]
    values = []
    for entry in df.transpose().to_dict().values():
        value = {}
        for k, v in entry.items():
            if not pd.isna(v):
                value[k] = v
        values.append(value)
    # insert these into files and remove these from the DeletedFile table
    # FIXME: When trying to restore this will cause problems if the foreign keys no
    #        longer exist
    query_all([insert(File).values(**v) for v in values] +
              [sdelete(DeletedFile).where(DeletedFile.id.in_(indexes))])
    set_working('pending_files')
    set_working('deleted_files')
    if refresh_processed:
        set_working('processed_files')
    compute_and_set_task.delay('pending_files')
    compute_and_set_task.delay('deleted_files')
    if refresh_processed:
        compute_and_set_task.delay('processed_files')
    return redirect(f"{url_for('file.root')}?activetab=nav-deleted")


# TODO: Figure out why there seems to be a delay in updating these within the view
# TODO: Put this code into view.py or somewhere more appropriate.
@bp.route('/process', methods=('POST',))
@login_required
def process():
    values = parse_request(request, table='File', rtype='process')
    ftype, uploads_id = values.pop('ftype'), values.pop('uploads_id')

    active_tab = 'nav-processed'
    if ftype == 'processed_files':
        update_files(values)
        set_working('processed_files')
        compute_and_set_task.delay('processed_files')

    if ftype == 'pending_files':
        active_tab = 'nav-pending-uploads'
        indexes = values.pop('indexes')
        df = get_value(f"vkey_{uploads_id}_pending_files")
        cdir, cdir_idx, cdir_count = resolve_directory(PROCESSED_DIRECTORY)
        moves, paths, names = [], [], []
        for idx in indexes:
            cdir, cdir_idx, cdir_count = check_directory_fullness(
                PROCESSED_DIRECTORY, cdir_idx, cdir_count
            )
            try:
                filepath = df.loc[df['id'] == idx, 'filepath'].iloc[0]
                name = df.loc[df['id'] == idx, 'filename'].iloc[0]
                if os.path.exists(filepath):
                    new_filepath = f"{cdir}/{secure_filename(os.path.basename(filepath))}"
                os.rename(filepath, new_filepath)
                paths.append(new_filepath)
                names.append(name)
                moves.append((filepath, new_filepath))
                cdir_count += 1
            except Exception as error:  # TODO: use specific errors
                # TODO: Flash this error with the files that didn't work to the user
                log.error(error)
        values['paths'] = paths
        values['names'] = names
        try:
            insert_files(values)
        except Exception as error:  # TODO: use specific errors
            # TODO: Flash this error and inform user of rollback
            log.error(error)
            # rollback all the renames
            for path_orig, path_new in moves:
                os.rename(path_new, path_orig)
        set_working('processed_files')
        set_working('pending_files')
        compute_and_set_task.delay('processed_files')
        compute_and_set_task.delay('pending_files')

    elif ftype == 'discovered_files':
        active_tab = 'nav-pending-discoveries'
        indexes = values.pop('indexes')
        df = get_value(f"vkey_{uploads_id}_discovered_files")
        touches, paths, names = [], [], []
        for idx in indexes:
            try:
                filepath = df.loc[df['id'] == idx, 'filepath'].iloc[0]
                name = os.path.basename(df.loc[df['id'] == idx, 'filename'].iloc[0])
                log.debug(filepath)
                log.debug(type(filepath))
                touch = f"{filepath}.touch"
                with open(touch, 'at') as fp:
                    pass
                touches.append(touch)
                paths.append(filepath)
                names.append(name)
            except Exception as error:  # TODO: use specific errors
                # TODO: Flash this error with the files that didn't work to the user
                log.error(error)

        values['paths'] = paths
        values['names'] = names
        try:
            insert_files(values)
        except Exception as error:  # TODO: use specific errors
            # TODO: Flash this error and inform user of rollback
            log.error(error)
            # rollback all the touches
            for touch in touches:
                os.remove(touch)
        set_working('processed_files')
        set_working('discovered_files')
        compute_and_set_task.delay('processed_files')
        compute_and_set_task.delay('discovered_files')

    # TODO: Implement this will take the information it needs from the form
    return redirect(f"{url_for('file.root')}?activetab={active_tab}")


@bp.route("/download", methods=('GET',))
@login_required
def download():
    request_values = request.values
    uploads_id = request_values.get('uploads_id')
    ftype = request_values['ftype']
    index = int(request_values['index'])
    df = get_value(ftype) if uploads_id is None else get_value(f"vkey_{uploads_id}_{ftype}")
    filepath, filename = tuple(
        df.loc[df['id'] == index, ['filepath', 'filename']].iloc[0]
    )
    filename = secure_filename(filename)
    return send_file(os.path.realpath(filepath), as_attachment=True,
                     download_name=filename)


@bp.route('/details', methods=('GET',))
@login_required
def details():
    request_values = request.values
    index = int(request_values['index'])
    data = file_details(index)
    if not data:
        return redirect(request.referrer)
    return render_template('file/details.html', data=data)


@bp.route('/', methods=('GET',))
@login_required
def root():
    request_values = request.values
    active_tab = request_values.get('activetab')
    if (active_tab is None) or (
        active_tab not in ['nav-processed', 'nav-pending-uploads',
                           'nav-pending-discoveries', 'nav-deleted']):
        active_tab = 'nav-processed'
    data = file_root()
    data['uploads_id'] = f"{current_user.username}.{data['timestamp_str']}"
    data['active_tab'] = active_tab
    return render_template('file/root.html', data=data)


# The routes below are used to execute background tasks
@bp.route("/refresh/<vkey>", methods=('GET',))
@login_required
def refresh(vkey: str):
    set_working(vkey)
    update_vkey(vkey)
    return make_response((f"Request for refresh submitted", 200))


@bp.route("/ready/<key>", methods=('GET',))
@login_required
def ready(key):
    is_ready = task_complete(key)
    return jsonify(dict(ready=is_ready))


@bp.route("/ajax", methods=('GET',))
@login_required
def ajax():
    # This routes below provide server-side computations for datatables (used by files)
    return jsonify(fetch(request))

# TODO: Take the chunking part out of this and put it into downloads, but keep it
#       commented out until there is time to implement it
# @bp.route("/download", methods=('GET',))
# @login_required
# def download():
#     request_values = request.values
#
#     uploads_id = request_values['uploads_id']
#     ftype = request_values['ftype']
#     index = int(request_values['index'])
#
#     df = get_value(f"vkey_{uploads_id}_{ftype}")
#     filepath, filename = tuple(
#         df.loc[df['id'] == index, ['filepath', 'filename']].iloc[0]
#     )
#     filename = secure_filename(filename)
#     s = send_file(os.path.realpath(filepath), as_attachment=True,
#                   download_name=filename)
#     header = {k: v for k, v in s.headers.items()}
#     def generate():
#         with open(os.path.realpath(filepath), 'rb') as f:
#             f.seek(0, os.SEEK_END)
#             size = f.tell()
#             for offset in range(0, size, CHUNK_SIZE):
#                 chunk = min(CHUNK_SIZE, size-offset)
#                 f.seek(offset)
#                 yield f.read(chunk)
#     return generate(), header

# @bp.route('/edit/<fid>', methods=('GET', 'POST'))
# @login_required
# def edit(fid: int):
#     data = file_edit(fid, request)
#     if request.method == 'GET' and data:
#         return render_template('file/edit.html', data=data)
#     elif request.method == 'POST':
#         return redirect(url_for('file.edit', fid=fid))
#     else:
#         return redirect(url_for('file.root'))