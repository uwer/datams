import flask
import pandas as pd
from functools import partial
from datams.utils import move_pending_files
from datams.celery import load_cache
from datams.db.requests import parse_request
from datams.db.utils import (mooring_add_equipment_html, mooring_files_add_section,
                             map_properties)
from datams.db.queries import select_query, insert_query, update_query, delete_query

import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

"""
This module acts as a layer between the database and the web application views, 
each view requiring database data has a method defined in here.  These methods follow 
the naming convention of `select_<view_name>_data().  The `select` portion of the name
indicates what actions the method is preforming and the `view_name` indicates the caller
finally the data portion represents what layer these functions belong to.  

How the methods work.  The view layer calls this layer to get the data it needs from the
database to render the html templates.  These methods therefore define what tables 
they want and forwarding the view information to the fetch_data method.  This maps all 
the variable names used by the templates to the function calls needed to collect that 
information from the database.  The view information (i.e. view name, relevant ids, and 
sometimes method).  

The fetch_data method also provides any last minute formatting to the data before 
returning it to the view layer.   
"""
# TODO: Currently the query layer is also preforming the formatting, but this should be
#       done here.
# TODO: Fillna with spaces in here when appropriate
# TODO: Definitions of what each column wants should probably start here and be passed
#       in to the low level functions


def fetch_data(requested_data, **kwargs):
    data_mapping = dict(
        contacts=partial(select_query, data='contact', **kwargs),
        contact=partial(select_query, data='contact', **kwargs),
        deployments=partial(select_query, data='deployment', **kwargs),
        deployment=partial(select_query, data='deployment', **kwargs),
        files=partial(select_query, data='file', **kwargs),
        file=partial(select_query, data='file', **kwargs),
        ofiles=partial(select_query, data='ofile', **kwargs),
        dfiles=partial(select_query, data='dfile', **kwargs),
        mfiles=partial(select_query, data='mfile', **kwargs),
        equipment=partial(select_query, data='equipment', **kwargs),
        moorings=partial(select_query, data='mooring', **kwargs),
        mooring=partial(select_query, data='mooring', **kwargs),
        organizations=partial(select_query, data='organization', **kwargs),
        organization=partial(select_query, data='organization', **kwargs),
        all_countries=partial(select_query, data='country'),
        all_contacts=partial(select_query, data='contact'),
        all_deployments=partial(select_query, data='deployment'),
        all_files=partial(select_query, data='file'),
        all_equipment=partial(select_query, data='equipment'),
        all_moorings=partial(select_query, data='mooring'),
        all_organizations=partial(select_query, data='organization'),
        all_positions=partial(select_query, data='contact_positions'),
        all_items=partial(select_query, data='equipment_items'),
        all_status=partial(select_query, data='equipment_status'),
        all_descriptions=partial(select_query, data='file_descriptions'),
        all_levels=partial(select_query, data='file_levels'),
        all_timezones=partial(select_query, data='timezones')
    )
    d = dict()
    t, v = kwargs.get('view', '.').split('.')
    if v in ('details', 'edit', 'download'):
        m = data_mapping[t]()
        if m.empty:
            return None
        else:
            requested_data.remove(t)
            d[t] = m.iloc[0].fillna('') if kwargs.get('method') == 'GET' else m.iloc[0]
    d.update({rd: data_mapping[rd]() for rd in requested_data})
    return d


def contact_root():
    kwargs = dict(view='contact.root')
    data_to_fetch = ['contacts', 'all_organizations', 'all_positions']
    return fetch_data(data_to_fetch, **kwargs)


def contact_details(cid):
    kwargs = dict(view='contact.details', contact_id=cid)
    data_to_fetch = ['contact', 'deployments']
    return fetch_data(data_to_fetch, **kwargs)


def contact_add(request: flask.Request):
    values = parse_request(request, table='Contact', rtype='add')
    insert_query(table='Contact', values=values)


def contact_edit(cid, request: flask.Request):
    if request.method == 'GET':
        kwargs = dict(view='contact.edit', contact_id=cid)
        data_to_fetch = ['contact', 'deployments', 'all_organizations',
                         'all_deployments', 'all_positions']
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='Contact', rtype='edit')
        update_query(table='Contact', values=values, contact_id=cid)


def contact_delete(cid):
    delete_query(table='Contact', contact_id=cid)


def deployment_root():
    kwargs = dict(view='deployment.root')
    data_to_fetch = ['deployments', 'all_countries', 'all_organizations']
    return fetch_data(data_to_fetch, **kwargs)


def deployment_details(did: int):
    kwargs = dict(view='deployment.details', deployment_id=did)
    data_to_fetch = [
        'deployment', 'organizations', 'moorings', 'equipment', 'contacts', 'dfiles',
        'mfiles', 'moorings']
    data = fetch_data(data_to_fetch, **kwargs)
    if data is None:
        return data
    data['moorings'] = mooring_add_equipment_html(data['moorings'], data['equipment'])
    data['mfiles'] = mooring_files_add_section(data['mfiles'], data['moorings'])
    data['map_center'], data['map_zoom'] = map_properties(data['moorings'])
    data['mfiles'] = data['mfiles'][['description', 'filename', 'section', 'url']]
    return data


def deployment_add(request: flask.Request):
    values = parse_request(request, table='Deployment', rtype='add')
    insert_query(table='Deployment', values=values)


def deployment_edit(did: int, request: flask.Request):
    if request.method == 'GET':
        kwargs = dict(view='deployment.edit', deployment_id=did)
        data_to_fetch = [
            'deployment', 'organization', 'contacts', 'moorings', 'all_countries',
            'all_organizations', 'all_contacts', 'all_deployments', 'all_timezones',
            'all_positions'
        ]
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='Deployment', rtype='edit')
        update_query(table='Deployment', values=values, deployment_id=did)
        load_cache()


def deployment_delete(did):
    delete_query(table='Deployment', deployment_id=did)
    load_cache()


def file_root():
    kwargs = dict(view='file.root')
    data_to_fetch = ['all_organizations', 'all_deployments', 'all_moorings',
                     'all_equipment', 'all_levels', 'all_descriptions']
    data = fetch_data(data_to_fetch, **kwargs)
    # don't actually pull files (it's too slow)
    data['files'] = pd.DataFrame(columns=['level', 'owner', 'description', 'filename',
                                          'uploaded', 'url'])
    return data


def file_details(fid):
    kwargs = dict(view='file.details', file_id=fid)
    return fetch_data(['file'], **kwargs)


def file_add(request: flask.Request, session: flask.session):
    values = parse_request(request, table='File', rtype='add')
    insert_query(table='File', values=values)
    move_pending_files(session)
    load_cache()


def file_edit(fid, request: flask.Request):
    if request.method == 'GET':
        kwargs = dict(view='file.edit', file_id=fid)
        data_to_fetch = ['file', 'all_organizations', 'all_deployments', 'all_moorings',
                         'all_equipment', 'all_levels', 'all_descriptions']
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='File', rtype='edit')
        update_query(table='File', values=values, file_id=fid)
        load_cache()


def file_delete(fid):
    delete_query(table='File', file_id=fid)
    load_cache()


def file_download(fid):
    kwargs = dict(view='file.download', file_id=fid)
    data_to_fetch = ['file']
    return fetch_data(data_to_fetch, **kwargs)


def equipment_root():
    kwargs = dict(view='equipment.root')
    data_to_fetch = ['equipment', 'all_organizations', 'all_items', 'all_status']
    return fetch_data(data_to_fetch, **kwargs)


def equipment_details(eid):
    kwargs = dict(view='equipment.details', equipment_id=eid)
    data_to_fetch = ['equipment', 'deployments']
    return fetch_data(data_to_fetch, **kwargs)


def equipment_add(request: flask.Request):
    values = parse_request(request, table='Equipment', rtype='add')
    insert_query(table='Equipment', values=values)


def equipment_edit(eid, request: flask.Request):
    if request.method == 'GET':
        kwargs = dict(view='equipment.edit', equipment_id=eid)
        data_to_fetch = ['equipment', 'deployments', 'all_deployments', 'all_organizations',
                          'all_items', 'all_status']
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='Equipment', rtype='edit')
        update_query(table='Equipment', values=values, equipment_id=eid)
        load_cache()


def equipment_delete(eid):
    delete_query(table='Equipment', equipment_id=eid)
    load_cache()


def mooring_root():
    kwargs = dict(view='mooring.root')
    data_to_fetch = ['moorings', 'all_deployments', 'all_timezones']
    return fetch_data(data_to_fetch, **kwargs)


def mooring_details(mid):
    kwargs = dict(view='mooring.details', mooring_id=mid)
    data_to_fetch = ['mooring', 'deployment', 'equipment', 'organizations', 'mfiles']
    return fetch_data(data_to_fetch, **kwargs)


def mooring_add(request: flask.Request):
    values = parse_request(request, table='Mooring', rtype='add')
    insert_query(table='Mooring', values=values)


def mooring_edit(mid, request: flask.Request):
    if request.method == 'GET':
        kwargs = dict(view='mooring.edit', mooring_id=mid)
        data_to_fetch = ['mooring', 'equipment', 'all_deployments', 'all_equipment',
                         'all_timezones']
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='Mooring', rtype='edit')
        update_query(table='Mooring', values=values, mooring_id=mid)
        load_cache()


def mooring_delete(mid):
    delete_query(table='Mooring', mooring_id=mid)
    load_cache()


def organization_root():
    kwargs = dict(view='organization.root')
    data_to_fetch = ['organizations', 'all_countries']
    return fetch_data(data_to_fetch, **kwargs)


def organization_details(oid: int):
    kwargs = dict(view='organization.details', organization_id=oid)
    data_to_fetch = ['organization', 'contacts', 'deployments', 'ofiles', 'equipment']
    return fetch_data(data_to_fetch, **kwargs)


def organization_add(request: flask.Request):
    values = parse_request(request, table='Organization', rtype='add')
    insert_query(table='Organization', values=values)


def organization_edit(oid: int, request: flask.request):
    if request.method == 'GET':
        kwargs = dict(view='organization.edit', organization_id=oid)
        data_to_fetch = [
            'organization', 'contacts', 'deployments', 'ofiles', 'equipment',
            'all_countries', 'all_contacts', 'all_deployments', 'all_status',
            'all_organizations', 'all_equipment', 'all_positions', 'all_items'
        ]
        return fetch_data(data_to_fetch, **kwargs)
    else:
        values = parse_request(request, table='Organization', rtype='edit')
        update_query(table='Organization', values=values, organization_id=oid)
        load_cache()


def organization_delete(oid):
    delete_query(table='Organization', organization_id=oid)
    load_cache()
