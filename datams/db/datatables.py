import flask
from datams.redis import get_value  # get_processed_files, get_discovered_files
import logging

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

"""
    # The draw counter that this object is a response to - from the draw parameter sent
    # as part of the data request. Note that it is strongly recommended for security
    # reasons that you cast this parameter to an integer, rather than simply echoing
    # back to the client what it sent in the draw parameter, in order to prevent Cross
    # Site Scripting (XSS) attacks.

    # Total records, before filtering (i.e. the total number of records in the database)

    # Total records, after filtering (i.e. the total number of records after filtering
    # has been applied - not just the number of records being returned for this page of
    # data).

    # The data to be displayed in the table. This is an array of data source objects,
    # one for each row, which will be used by DataTables. Note that this parameter's
    # name can be changed using the ajax option's dataSrc property.

    # Optional: If an error occurs during the running of the server-side processing
    # script, you can inform the user of this error by passing back the error message to
    # be displayed using this parameter. Do not include if there is no error.
    # response['error']
"""


def processed_files(request: flask.Request):
    cmap = {0: 'level', 1: 'owner', 2: 'description', 3: 'filename', 4: 'uploaded',
            5: 'url'}
    icmap = {v: k for k, v in cmap.items()}

    request_values = request.values

    draw = request_values['draw']
    start = int(request_values['start'])
    length = int(request_values['length'])
    column_attributes = {}

    for k, v in request_values.items():
        if k.startswith('columns'):
            if k.endswith('[orderable]'):
                key = 'orderable'
                cidx = int(k[8:-12])
                cargs = column_attributes.get(cidx, dict())
                cargs[key] = False if v == 'false' else True
                column_attributes[cidx] = cargs
            elif k.endswith('[searchable]'):
                key = 'searchable'
                cidx = int(k[8:-13])
                cargs = column_attributes.get(cidx, dict())
                cargs[key] = False if v == 'false' else True
                column_attributes[cidx] = cargs
    df = get_value('processed_files')
    df = df.drop(columns=['id'])
    search_value = request_values['search[value]']
    if search_value != '':
        for i in ['.', '+', '?', '^', '$', '|', '&']:
            search_value = search_value.replace(i, f"\\{i}")
        re = '^' + ''.join([f"(?=.*{w})" for w in search_value.split(' ') if w != ''])
        searchable = df.assign(
            a = df['level'] + ' ' + df['owner'] + ' ' + df['description'] + ' '
                + ' ' + df['filename'] + ' ' + ' ' + df['uploaded']
        )['a']
        df_filtered = df.loc[searchable.str.contains(re, case=False), :]
    else:
        df_filtered = df

    by = []
    ascending = []
    cidx = int(request_values['order[0][column]'])
    if column_attributes[cidx]['orderable']:
        by.append(cmap[cidx])
        ascending.append(request_values['order[0][dir]'] == 'asc')

    if not df.empty:
        df_filtered = df_filtered.sort_values(by=by, ascending=ascending,
                                              key=lambda x: x.str.lower())
    end = start + length if length != -1 else df.shape[0]
    data = list(
        df_filtered.iloc[start:end]
        .rename(columns=icmap)
        .transpose()
        .to_dict()
        .values()
    )
    response = dict(
        draw=draw,
        recordsTotal=df.shape[0],
        recordsFiltered=df_filtered.shape[0],
        data=data,
    )
    return response


def discovered_files(request: flask.Request):
    cmap = {0: 'filename', 1: 'last_modified'}
    icmap = {v: k for k, v in cmap.items()}

    request_values = request.values

    draw = request_values['draw']
    start = int(request_values['start'])
    length = int(request_values['length'])
    column_attributes = {}

    for k, v in request_values.items():
        if k.startswith('columns'):
            if k.endswith('[orderable]'):
                key = 'orderable'
                cidx = int(k[8:-12])
                cargs = column_attributes.get(cidx, dict())
                cargs[key] = False if v == 'false' else True
                column_attributes[cidx] = cargs
            elif k.endswith('[searchable]'):
                key = 'searchable'
                cidx = int(k[8:-13])
                cargs = column_attributes.get(cidx, dict())
                cargs[key] = False if v == 'false' else True
                column_attributes[cidx] = cargs
    df = get_value('discovered_files')
    search_value = request_values['search[value]']
    if search_value != '':
        for i in ['.', '+', '?', '^', '$', '|', '&']:
            search_value = search_value.replace(i, f"\\{i}")
        re = '^' + ''.join([f"(?=.*{w})" for w in search_value.split(' ') if w != ''])
        searchable = df.assign(a=df['file'] + ' ' + df['last_modified'])['a']
        df_filtered = df.loc[searchable.str.contains(re, case=False), :]
    else:
        df_filtered = df

    by = []
    ascending = []
    cidx = int(request_values['order[0][column]'])
    if column_attributes[cidx]['orderable']:
        by.append(cmap[cidx])
        ascending.append(request_values['order[0][dir]'] == 'asc')

    if not df.empty:
        df_filtered = df_filtered.sort_values(by=by, ascending=ascending,
                                              key=lambda x: x.str.lower())

    end = start + length if length != -1 else df.shape[0]
    data = list(
        df_filtered.iloc[start:end]
        .rename(columns=icmap)
        .transpose()
        .to_dict()
        .values()
    )
    response = dict(
        draw=draw,
        recordsTotal=df.shape[0],
        recordsFiltered=df_filtered.shape[0],
        data=data,
    )
    return response
