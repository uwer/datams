import flask
from datams.redis import get_value
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


# TODO: Wrap the common bits into functions for reuse
def fetch(request: flask.Request):
    column_maps = dict(
        processed_files={
            0: 'level', 1: 'filename', 2: 'owner', 3: 'description', 4: 'uploaded',
            5: 'url', 100: 'id'  # 101: 'name',  100: 'filepath'
        },
        pending_files={
            0: 'filename', 1: 'uploaded', 2: 'uploaded_by', 100: 'id'
            # 101: 'name', 100: 'filepath'
        },
        discovered_files={
            0: 'filename', 1: 'last_modified', 100: 'id'  # 101: 'name', 100: 'filepath'
        },
        deleted_files={
            0: 'filename', 1: 'deleted', 2: 'deleted_by', 3: 'originally_uploaded_by',
            100: 'id'  # 101: 'name', 100: 'filepath'
        },
    )
    request_values = request.values

    uploads_id = request_values['uploads_id']
    ftype = request_values['ftype']
    draw = request_values['draw']
    start = int(request_values['start'])
    length = int(request_values['length'])

    cmap = column_maps[ftype]
    icmap = {v: k for k, v in cmap.items()}

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
    df = get_value(f"vkey_{uploads_id}_{ftype}")[[v for v in cmap.values()]]
    # log.debug(df.columns)
    # log.debug(" + ' ' + ".join(
    #             [f"df['{i}']" for i in cmap.values()
    #              if i != 'url' and i != 'filepath' and i != 'name']))
    search_value = request_values['search[value]']
    if search_value != '':
        for i in ['.', '+', '?', '^', '$', '|', '&']:
            search_value = search_value.replace(i, f"\\{i}")
        re = '^' + ''.join([f"(?=.*{w})" for w in search_value.split(' ') if w != ''])
        searchable = df.assign(
            a=eval(" + ' ' + ".join(
                [f"df['{i}'].astype(str)" for i in cmap.values()
                 if i != 'url' and i != 'filepath' and i != 'name'])
            )
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
