import os
import datetime as dt
from flask import (Blueprint, render_template, request, redirect, url_for, send_file,
                   jsonify, make_response)
from flask_login import login_required, current_user
from datams.celery import (update_task, compute_and_set_task, task_complete, update_vkey)
from datams.redis import get_value
from datams.db.views import (file_root, file_details, file_edit, file_download,
                             file_delete)  # file_add, file_pending
from datams.db.requests import parse_request
from datams.db.datatables import fetch
from datams.utils import PENDING_DIRECTORY, PROCESSED_DIRECTORY
from werkzeug.utils import secure_filename
from datams.db.queries.insert import insert_files
from datams.db.queries.update import update_files
import logging

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

DIRECTORY_LIMIT = 65000


bp = Blueprint('file', __name__, url_prefix='/file')

PROCESSED_FILES = None
PENDING_FILES = None
DISCOVERED_FILES = None
DELETED_FILES = None


def resolve_filename(filename, directory):
    i = 0
    new_filename = filename
    while new_filename in os.listdir(directory):
        fl = filename.split('.')
        new_filename = (f"{'.'.join(fl[:-1])} ({i}).{fl[-1]}"
                        if len(fl) > 1 else f"{filename} ({i})")
        i += 1
    return new_filename


def is_int_directory(directory):
    try:
        int(directory)
    except TypeError:
        return False
    return True


def check_directory_fullness(root_dir, cdir_idx, cdir_count):
    cdir = f"{root_dir}/{cdir_idx}"
    while cdir_count >= DIRECTORY_LIMIT:
        cdir_idx += 1
        cdir = f"{root_dir}/{cdir_idx}"
        os.makedirs(cdir, exist_ok=True)
        cdir_count = len(os.listdir(cdir))
    return cdir, cdir_idx, cdir_count


def resolve_directory(root_dir):
    int_dirs = [i for i in os.listdir(root_dir)
                if os.path.isdir(f"{root_dir}/{i}") and is_int_directory(i)]
    cdir_idx = max(int_dirs) if int_dirs else 0
    cdir = f"{root_dir}/{cdir_idx}"
    if not int_dirs:
        os.makedirs(cdir, exist_ok=True)
    cdir_count = len(os.listdir(cdir))
    return check_directory_fullness(root_dir, cdir_idx, cdir_count)


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
    return redirect(request.referrer)


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


# TODO: Figure out why there seems to be a delay in updating these within the view
# TODO: Put this code into view.py or somewhere more appropriate.
@bp.route('/process', methods=('POST',))
@login_required
def process():
    values = parse_request(request, table='File', rtype='process')
    ftype, uploads_id = values.pop('ftype'), values.pop('uploads_id')

    if ftype == 'processed_files':
        update_files(values)

    if ftype == 'pending_files':
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

    elif ftype == 'discovered_files':
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

    compute_and_set_task.delay('pending_files')
    compute_and_set_task.delay('discovered_files')
    compute_and_set_task.delay('processed_files')
    # TODO: Implement this will take the information it needs from the form
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
    data = file_root()
    data['uploads_id'] = f"{current_user.username}.{data['timestamp_str']}"
    # create_file_vkeys_task.delay(data['uploads_id'])
    return render_template('file/root.html', data=data)


# The routes below are used to execute background tasks
@bp.route("/refresh/<vkey>", methods=('GET',))
@login_required
def refresh(vkey: str):
    update_vkey(vkey)
    return make_response((f"Request for refresh submitted", 200))


@bp.route("/ready/<vkey>", methods=('GET',))
@login_required
def ready(vkey):
    is_ready = task_complete(vkey)
    return jsonify(dict(ready=is_ready))


@bp.route("/ajax", methods=('GET',))
@login_required
def ajax():
    # This routes below provide server-side computations for datatables (used by files)
    return jsonify(fetch(request))



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

# @bp.route("/ajax_processed", methods=('GET',))
# @login_required
# def ajax_processed():
#     return jsonify(fetch('processed_files', request))
#
#
# @bp.route("/ajax_pending", methods=('GET',))
# @login_required
# def ajax_pending():
#     return jsonify(fetch('pending_files', request))
#
#
# @bp.route("/ajax_discovered", methods=('GET',))
# @login_required
# def ajax_discovered():
#     return jsonify(fetch('discovered_files', request))
#
#
# @bp.route("/ajax_deleted", methods=('GET',))
# @login_required
# def ajax_deleted():
#     return jsonify(fetch('deleted_files', request))


# # The routes below provide server-side options for datatables
# @bp.route("/processed_datatable", methods=('GET',))
# @login_required
# def processed_datatable():
#     return jsonify(processed_files(request))
#
#
# @bp.route("/discovered_datatable", methods=('GET',))
# @login_required
# def discovered_datatable():
#     return jsonify(discovered_files(request))



# @bp.route('/process', methods=('POST',))
# @login_required
# def process_orig():
#     values = parse_request(request, table='File', rtype='process')
#
#     ftype = values.pop('ftype')
#     filepaths = [f for f in reversed(values.pop('filepaths'))]
#     filenames = values.pop('filenames')
#
#     assert len(filepaths) == len(filenames)
#     end_idx = len(filepaths) - 1
#
#     if ftype == 'processed_files':
#         # update the entry in the database with new details
#         # template can then call the refresh method (for the table)
#         pass
#
#     if ftype == 'pending_files':
#         # figure out what the largest number directory is in the processed directory
#         all_dirs = [i for i in os.listdir(PROCESSED_DIRECTORY)
#                     if os.path.isdir(f"{PROCESSED_DIRECTORY}/{i}")]
#         final_dirs = []
#         for d in all_dirs:
#             try:
#                 final_dirs.append(int(d))
#             except TypeError:
#                 pass
#
#         curr_dir_index = max(final_dirs) if final_dirs else 0
#         curr_dir = f"{PROCESSED_DIRECTORY}/{curr_dir_index}"
#         if not final_dirs:
#             os.makedirs(curr_dir)
#         curr_dir_count = len(os.listdir(curr_dir))
#
#         new_filepaths = []
#         for idx, path in enumerate(filepaths):
#             if os.path.exists(path):
#                 file = secure_filename(os.path.basename(path))
#                 curr_dir_count += 1
#                 if curr_dir_count > 65000:
#                     curr_dir_index += 1
#                     curr_dir = f"{PROCESSED_DIRECTORY}/{curr_dir_index}"
#                     os.makedirs(curr_dir)
#                     curr_dir_count = 0
#                 try:
#                     new_path = f"{curr_dir}/{file}"
#                     os.rename(path, new_path)
#                     new_filepaths.append(new_path)
#                 except Exception as error:  # should make this more specific
#                     curr_dir_count -= 1
#                     filenames.pop(end_idx - idx)
#                     log.error(error)
#             else:
#                 filenames.pop(end_idx - idx)
#
#         values['paths'] = [f for f in reversed(new_filepaths)]
#         values['names'] = filenames
#         insert_files(values)
#         # TODO: Refresh the pending and processed file lists
#
#
#         # from the current number of files in the submitted directory
#         # if it is greater than
#         # for each file
#         # try moving the file into the pro
#         # move the file to the processed file directory
#
#
#     if ftype == 'discovered_files':
#         pass
#         # log.debug(values['tid'])
#         # log.debug(values['paths'])
#         # values['description']
#         # values['comments']
#         # values['level']
#         # values['uploaded']
#
#     # TODO: Implement this will take the information it needs from the form
#     return redirect(request.referrer)


# # TODO: Put this code into view.py or somewhere more appropriate.
# @bp.route('/process', methods=('POST',))
# @login_required
# def process_orig2():
#     values = parse_request(request, table='File', rtype='process')
#     ft, fp, fn = values.pop('ftype'), values.pop('filepaths'), values.pop('filenames')
#     assert len(fp) == len(fn)
#     if ft == 'pending_files':
#         df = get_value('pending_files')
#         filepaths, filenames, renames, skipped = [], [], [], []
#         cdir, cdir_idx, cdir_count = resolve_directory(PROCESSED_DIRECTORY)
#         for idx, p in enumerate(fp):
#             cdir, cdir_idx, cdir_count = check_directory_fullness(
#                 PROCESSED_DIRECTORY, cdir_idx, cdir_count
#             )
#             if os.path.exists(p) and p in list(df['path']):
#                 file = secure_filename(os.path.basename(p))
#                 new_path = f"{cdir}/{file}"
#                 # TODO: Have a way to roll this back if the database insertion fails
#                 try:
#                     os.rename(p, new_path)
#                     renames.append((new_path, p))
#                     filepaths.append(new_path)
#                     filenames.append(fn[idx])
#                     cdir_count += 1
#                 except Exception as error:  # TODO: use specific errors
#                     log.error(error)
#             else:
#                 skipped.append(fn[idx])
#
#         values['paths'] = filepaths
#         values['names'] = filenames
#         try:
#             insert_files(values)
#         except Exception as error:  # TODO: use specific errors
#             log.error(error)
#             # rollback all the renames
#             for new_path, old_path in renames:
#                 os.rename(new_path, old_path)
#
#         # TODO: Refresh the pending and processed file lists
#
#     elif ft == 'processed_files':
#         # update the entry in the database with new details
#         # template can then call the refresh method (for the table)
#         pass
#
#         # from the current number of files in the submitted directory
#         # if it is greater than
#         # for each file
#         # try moving the file into the pro
#         # move the file to the processed file directory
#
#
#     if ft == 'discovered_files':
#         pass
#
#     # TODO: Implement this will take the information it needs from the form
#     return redirect(request.referrer)