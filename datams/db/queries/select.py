import os
import datetime as dt
from pathlib import Path
import pandas as pd
from sqlalchemy import select, text, func, literal_column, String

from datams.utils import (MENU_CONFIG, TIMEZONES, DISCOVERY_DIRECTORY,
                          PENDING_DIRECTORY, DELETED_DIRECTORY)
from datams.db.core import query_df, query_first_df, query_first
from datams.db.tables import (
    Contact, Country, Deployment, DeploymentContact, DeploymentOrganization, File,
    Equipment, Mooring, MooringEquipment, Organization, User, FILE_LEVELS
)
from datams.db.formatting import (
    contact_format, deployment_format, organization_format, mooring_format,
    equipment_format, file_format
)

import logging

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# TODO: Add sorting to here or data_for_views where appropriate
# TODO: Rename occurances of file/files (that correspond to processed files) to
#       processed_file/processed_files respectively
"""
This file act as the layer immediately interacting with the database, currently it is 
doing formatting and defining what columns it needs from the database, but this is a 
poor design instead I want to:
    1) pass into these methods what columns it wants from the database and which to 
       compute
    2) pull the formatting part out of here and put it into datams.db.data instead it 
       should communicate with select and datams.db.formatting 
"""


def select_query(data, **kwargs):
    if data == 'contact':
        return select_contacts(**kwargs)
    elif data == 'deployment':
        return select_deployments(**kwargs)
    elif data == 'file':
        return select_files(**kwargs)
    elif data == 'ofile':
        return select_ofiles(**kwargs)
    elif data == 'dfile':
        return select_dfiles(**kwargs)
    elif data == 'mfile':
        return select_mfiles(**kwargs)
    elif data == 'processed_files':
        return select_processed_files()
    elif data == 'pending_files':
        return select_pending_files()
    elif data == 'discovered_files':
        return select_discovered_files()
    elif data == 'deleted_files':
        return select_deleted_files()
    elif data == 'equipment':
        return select_equipment(**kwargs)
    elif data == 'mooring':
        return select_moorings(**kwargs)
    elif data == 'organization':
        return select_organizations(**kwargs)
    elif data == 'country':
        return select_countries()
    elif data == 'contact_positions':
        return select_contact_positions()
    elif data == 'equipment_items':
        return select_equipment_items()
    elif data == 'equipment_status':
        return select_equipment_status()
    elif data == 'file_descriptions':
        return select_file_descriptions()
    elif data == 'file_levels':
        return select_file_levels()
    elif data == 'timezones':
        return select_timezones()
    else:
        raise NotImplementedError


def _get_file_level(file_id):
    df = query_df(
        select(File.organization_id, File.deployment_id, File.mooring_equipment_id)
        .where(File.id == file_id)
    )
    if df.empty:
        return None
    elif not pd.isna(df.iloc[0]['organization_id']):
        return 'organization'
    elif not pd.isna(df.iloc[0]['deployment_id']):
        return 'deployment'
    elif not pd.isna(df.iloc[0]['mooring_equipment_id']):
        return 'mooring_equipment'
    else:
        return 'unowned'


def next_deployment_id():
    stmt = text(f'''SELECT last_value FROM "Deployment_id_seq";''')
    return int(query_first_df(stmt)['last_value'])


def select_processed_files():
    df = pd.concat(
        [select_ufiles(), select_ofiles(), select_dfiles(), select_mfiles()]
    ).reset_index(drop=True)
    df = df[['id', 'level', 'filename', 'owner', 'description', 'uploaded',
             'url', 'path']]
    return df.drop(columns=['id']).rename(columns={'path': 'filepath'})


def select_pending_files():
    temp = [(f"{PENDING_DIRECTORY}/{f}", f) for f in os.listdir(PENDING_DIRECTORY)
            if os.path.isfile(f"{PENDING_DIRECTORY}/{f}") and not f.startswith('.temp')]
    filepaths = [p for p, _ in temp]
    filenames = [f for _, f in temp]
    # last_modifies = [
    #     dt.datetime.fromtimestamp(
    #         os.path.getmtime(f"{PENDING_DIRECTORY}/{f}")
    #     ).strftime('%Y-%m-%d %H:%M:%S') for f in files
    # ]
    uploaded = [
        dt.datetime.fromtimestamp(
            float(f"{f.split('.')[1][:-6]}.{f.split('.')[1][-6:]}")
        ).strftime('%Y-%m-%d %H:%M:%S') for f in filenames
    ]
    uploaded_bys = [f.split('.')[0] for f in filenames]
    filenames = ['.'.join(f.split('.')[2:]) for f in filenames]
    return pd.DataFrame({'filepath': filepaths, 'filename': filenames,
                         'uploaded': uploaded, 'uploaded_by': uploaded_bys})


def select_discovered_files():
    """
    p = pathlib.Path('/First/Second/Third/Fourth/Fifth')
    p.parts[2:]
    ('Second', 'Third', 'Fourth', 'Fifth')
    pathlib.Path(*p.parts[2:])
    PosixPath('Second/Third/Fourth/Fifth')

    """
    touched_files = []
    normal_files = set([
        str(f) if not str(f).endswith('.touch') else touched_files.append(str(f)[:-6])
        for f in Path(DISCOVERY_DIRECTORY).rglob('*')
        if f.is_file()
    ])
    if None in normal_files:
        normal_files.remove(None)
    filepaths = sorted(list(normal_files.difference(touched_files)))
    log.debug(len(Path(DISCOVERY_DIRECTORY).parts))
    filenames = [
        str(Path(*Path(f).parts[len(Path(DISCOVERY_DIRECTORY).parts):]))
        for f in filepaths
    ]
    last_modifies = [
        dt.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
        for f in filepaths
    ]
    return pd.DataFrame({'filepath': filepaths, 'filename': filenames,
                         'last_modified': last_modifies})


def select_deleted_files():
    temp = [(f"{DELETED_DIRECTORY}/{f}", f) for f in os.listdir(DELETED_DIRECTORY)
            if os.path.isfile(f"{DELETED_DIRECTORY}/{f}")]
    filepaths = [p for p, _ in temp]
    filenames = [f for _, f in temp]
    deleted = [
        dt.datetime.fromtimestamp(
            float(f"{f.split('.')[1][:-6]}.{f.split('.')[1][-6:]}")
        ).strftime('%Y-%m-%d %H:%M:%S') for f in filenames
    ]
    deleted_bys = [f.split('.')[0] for f in filenames]
    uploaded_bys = [f.split('.')[2] for f in filenames]
    filenames = ['.'.join(f.split('.')[2:]) for f in filenames]
    return pd.DataFrame({'filepath': filepaths, 'filename': filenames,
                         'deleted': deleted, 'deleted_by': deleted_bys,
                         'originally_uploaded_by': uploaded_bys})


def select_mooring_equipment_id(mooring_id: int, equipment_id: int):
    result = query_first_df(
        select(MooringEquipment.id)
        .where(MooringEquipment.mooring_id == mooring_id)
        .where(MooringEquipment.equipment_id == equipment_id)
    )
    return int(result['id'])


def select_contact_positions():
    return sorted(MENU_CONFIG['CONTACT_POSITIONS'])


def select_equipment_items():
    return sorted(MENU_CONFIG['EQUIPMENT_ITEMS'])


def select_equipment_status():
    return sorted(MENU_CONFIG['EQUIPMENT_STATUS'])


def select_file_descriptions():
    return sorted(MENU_CONFIG['FILE_DESCRIPTIONS'])


def select_timezones():
    return TIMEZONES


def select_file_levels():
    return FILE_LEVELS


def select_countries():
    return query_df(select(Country.id, Country.name)).sort_values(by='name')


def select_user(view, **kwargs):
    query_def = {
        'load_user': User.id == kwargs.get('user_id'),
        'authenticate_user': User.email == kwargs.get('user_email'),
    }
    stmt = select(User)
    where = query_def[view]
    stmt = stmt if where is None else stmt.where(where)
    return query_first(stmt)


def select_contacts(view=None, **kwargs):
    v = 'None' if view is None else view
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'name'], None),
        'deployment.edit':
            (['id'], Deployment.id == kwargs.get('deployment_id')),
        'organization.edit':
            (['id'], Organization.id == kwargs.get('organization_id')),
        'organization.details':
            (['name', 'position', 'phone', 'email', 'avatar', 'url'],
             Organization.id == kwargs.get('organization_id')),
        'contact.root':
            (['name', 'organization', 'position', 'email', 'phone', 'url'], None),
        'contact.details':
            (['id', 'name', 'organization', 'position', 'email', 'phone', 'avatar',
              'comments'], Contact.id == kwargs.get('contact_id')),
        'contact.edit':
            (['id', 'name', 'first_name', 'last_name', 'position', 'email', 'phone',
              'avatar', 'comments', 'organization_id'],
             Contact.id == kwargs.get('contact_id')),
        'deployment.details':
            (['name', 'organization', 'position', 'email', 'phone', 'avatar', 'url'],
             Deployment.id == kwargs.get('deployment_id'))
    }
    stmt = (
        select(
            Contact.id, Contact.first_name, Contact.last_name, Contact.position,
            Contact.email, Contact.phone, Contact.organization_id, Contact.comments,
            Contact.avatar, Organization.abbreviation.label('organization'))
        .outerjoin(Organization)
        .outerjoin_from(Contact, DeploymentContact)
        .outerjoin_from(DeploymentContact, Deployment)
    )
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(Contact, Organization)
    return contact_format(query_df(stmt), compute=['name', 'url'])[c]


def select_organizations(view=None, **kwargs):
    v = 'None' if view is None else view
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'name'], None),
        'deployment.details':
            (['name', 'url'], Deployment.id == kwargs.get('deployment_id')),
        'deployment.edit':
            (['id'], Deployment.id == kwargs.get('deployment_id')),
        'mooring.details':
            (['name', 'url'], Mooring.id == kwargs.get('mooring_id')),
        'organization.root':
            (['name', 'abbreviation', 'country', 'url'], None),
        'organization.details':
            (['id', 'name', 'abbreviation', 'country', 'comments'],
             Organization.id == kwargs.get('organization_id')),
        'organization.edit':
            (['id', 'name', 'abbreviation', 'country_id', 'comments'],
             Organization.id == kwargs.get('organization_id')),
    }
    stmt = (
        select(Organization.id, Organization.name, Organization.abbreviation,
               Organization.country_id, Organization.comments,
               Country.name.label('country'))
        .join(Country)
        .outerjoin_from(Organization, DeploymentOrganization)
        .outerjoin_from(DeploymentOrganization, Deployment)
        .outerjoin_from(Deployment, Mooring)
    )
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(Organization, Country)
    return organization_format(query_df(stmt), compute=['url'])[c]


def select_deployments(view=None, **kwargs):
    v = 'None' if view is None else view
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'name', 'date', 'region', 'organizations', 'oids'], None),
        'contact.details':
            (['name', 'url'], Contact.id == kwargs.get('contact_id')),
        'contact.edit':
            (['id'], Contact.id == kwargs.get('contact_id')),
        'deployment.root':
            (['date', 'location', 'organizations', 'url'], None),
        'deployment.details':
            (['id', 'name', 'date', 'organizations', 'location', 'comments'],
             Deployment.id == kwargs.get('deployment_id')),
        'deployment.edit':
            (['id', 'region', 'location', 'date', 'country', 'comments',
              'organizations', 'country_id', 'oids'],
             Deployment.id == kwargs.get('deployment_id')),
        'equipment.details':
            (['name', 'organizations', 'url'],
             Equipment.id == kwargs.get('equipment_id')),
        'equipment.edit':
            (['id'], Equipment.id == kwargs.get('equipment_id')),
        'mooring.details':
            (['name', 'url'], Mooring.id == kwargs.get('mooring_id')),
        'organization.details':
            (['location', 'date', 'organizations', 'url'],
             Organization.id == kwargs.get('organization_id')),
        'organization.edit':
            (['id'], Organization.id == kwargs.get('organization_id')),
    }
    stmt = (
        select(
            Deployment.id, Deployment.region, Deployment.country_id,
            Deployment.comments, Country.name.label('country'),
            func.min(Mooring.deployed).label('date'),
            func.string_agg(Organization.abbreviation.distinct(),
                            literal_column("','")).label('organizations'),
            func.string_agg(func.cast(Organization.id, String).distinct(),
                            literal_column("','")).label('oids'))
        .outerjoin_from(Deployment, Mooring)
        .join_from(Deployment, Country)
        .join_from(Deployment, DeploymentOrganization)
        .join_from(DeploymentOrganization, Organization)
        .outerjoin_from(Deployment, DeploymentContact)
        .outerjoin_from(DeploymentContact, Contact)
        .outerjoin_from(Mooring, MooringEquipment)
        .outerjoin_from(MooringEquipment, Equipment)
    )

    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(Deployment, Country)
    return deployment_format(query_df(stmt), compute=['url', 'name', 'location'])[c]


def select_moorings(view=None, **kwargs):
    v = 'None' if view is None else view
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'latitude', 'longitude', 'did'], None),
        'deployment.details':
            (['id', 'latitude', 'longitude', 'deployed', 'recovered', 'seafloor_depth',
              'line_length', 'eq_items', 'eq_sns', 'eq_ids', 'name', 'icon', 'color',
              'url', 'html'], Deployment.id == kwargs.get('deployment_id')),
        'deployment.edit':
            (['deployed', 'recovered', 'latitude', 'longitude', 'url'],
             Deployment.id == kwargs.get('deployment_id')),
        'mooring.root':
            (['deployment', 'name', 'deployed', 'recovered', 'latitude', 'longitude',
              'url'], None),
        'mooring.details':
            (['id', 'deployed', 'recovered', 'timezone', 'latitude', 'longitude',
              'seafloor_depth', 'line_length', 'comments'],
             Mooring.id == kwargs.get('mooring_id')),
        'mooring.edit':
            (['id', 'deployed', 'recovered', 'timezone', 'latitude', 'longitude',
              'seafloor_depth', 'line_length', 'comments', 'deployment_id'],
             Mooring.id == kwargs.get('mooring_id')),
    }
    stmt = (
        select(
            Mooring.id, Mooring.deployed, Mooring.recovered, Mooring.timezone,
            Mooring.latitude, Mooring.longitude, Mooring.seafloor_depth,
            Mooring.line_length, Mooring.comments, Mooring.deployment_id,
            Mooring.deployment_id.label('did'),  # TODO: remove dependancy to this alias
            Deployment.region.label('dep_reg'), Country.name.label('dep_cou'),
            func.string_agg(Organization.abbreviation.distinct(),
                            literal_column("','")).label('dep_orgs'),
            func.string_agg(Equipment.item,
                            literal_column("','")).label('eq_items'),
            func.string_agg(Equipment.serial_number,
                            literal_column("','")).label('eq_sns'),
            func.string_agg(func.cast(Equipment.id, String),
                            literal_column("','")).label('eq_ids'))
        .join_from(Mooring, Deployment)
        .join_from(Deployment, Country)
        .join_from(Deployment, DeploymentOrganization)
        .join_from(DeploymentOrganization, Organization)
        .outerjoin_from(Mooring, MooringEquipment)
        .outerjoin_from(MooringEquipment, Equipment)
    )
    to_compute = ['name', 'icon', 'color', 'url', 'html', 'edit_url', 'deployment']
                  # ['latitude', 'longitude', 'seafloor_depth', 'line_length']
    # TODO: change dep_cou, dep_reg, dep_orgs, eq_items, equ_sns, equ_ids to the full
    #       names (i.e. deployment_country, deployment_region, deployment_organizations,
    #       etc.)
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(Mooring, Deployment, Country)
    return mooring_format(query_df(stmt), compute=to_compute)[c]


def select_equipment(view=None, **kwargs):
    v = 'None' if view is None else view
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'item', 'serial_number', 'mids'], None),
        'deployment.details':
            (['id', 'serial_number', 'item', 'make', 'model', 'comments', 'url',
              'html'], Deployment.id == kwargs.get('deployment_id')),
        'equipment.root':
            (['item', 'make_&_model', 'serial_number', 'status', 'url'], None),
        'equipment.details':
            (['id', 'serial_number', 'item', 'make_&_model', 'status', 'owner',
              'comments'], Equipment.id == kwargs.get('equipment_id')),
        'equipment.edit':
            (['id', 'serial_number', 'item', 'make', 'model', 'status', 'owner',
              'comments', 'organization_id'], Equipment.id == kwargs.get('equipment_id')),
        'mooring.details':
            (['name', 'url'], Mooring.id == kwargs.get('mooring_id')),
        'mooring.edit':
            (['id'], Mooring.id == kwargs.get('mooring_id')),
        'organization.details':
            (['name', 'url'], Organization.id == kwargs.get('organization_id')),
        'organization.edit':
            (['id'], Organization.id == kwargs.get('organization_id')),
    }
    stmt = (
        select(
            Equipment.id, Equipment.serial_number, Equipment.item,
            Equipment.make, Equipment.model, Equipment.status,
            Equipment.comments, Equipment.organization_id,
            Organization.abbreviation.label('owner'),
            func.string_agg(func.cast(Mooring.id, String).distinct(),
                            literal_column("','")).label('mids'))
        .outerjoin_from(Equipment, Organization)
        .outerjoin_from(Equipment, MooringEquipment)
        .outerjoin_from(MooringEquipment, Mooring)
        .outerjoin_from(Mooring, Deployment)
    )
    to_compute = ['make_&_model', 'url', 'html', 'name']
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(Equipment, Organization)
    return equipment_format(query_df(stmt), compute=to_compute)[c]


def select_ufiles(view=None, **kwargs):
    v = 'None' if view is None else view
    fid = None if 'file_id' not in kwargs else File.id == kwargs.get('file_id')
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'level', 'owner', 'description', 'filename', 'uploaded', 'comments',
              'path', 'url', 'organization_id', 'deployment_id', 'mooring_id', 'name',
              'equipment_id', 'mooring_equipment_id'], fid),
    }
    stmt = (
        select(
            File.id, File.description, File.path, File.name, File.uploaded,
            File.comments, File.organization_id, File.deployment_id,
            File.mooring_equipment_id)
        .where(File.organization_id == None)
        .where(File.deployment_id == None)
        .where(File.mooring_equipment_id == None)
    )
    to_compute = ['owner', 'filename', 'url', 'level']
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    df = file_format(query_df(stmt), compute=to_compute, level='unowned')
    df[['mooring_id', 'equipment_id']] = None
    return df[c]


def select_ofiles(view=None, **kwargs):
    v = 'None' if view is None else view
    fid = None if 'file_id' not in kwargs else File.id == kwargs.get('file_id')
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'level', 'owner', 'description', 'filename', 'uploaded', 'comments',
              'path', 'url', 'organization_id', 'deployment_id', 'mooring_id', 'name',
              'equipment_id', 'mooring_equipment_id'], fid),
        'organization.details':
            (['description', 'filename', 'uploaded', 'url', 'name'],
             Organization.id == kwargs.get('organization_id')),
        'organization.edit':
            (['id'], Organization.id == kwargs.get('organization_id')),
    }
    stmt = (
        select(
            File.id, File.description, File.path, File.name, File.uploaded,
            File.comments, File.organization_id, File.deployment_id,
            File.mooring_equipment_id, Organization.abbreviation.label('org'))
        .join(Organization)
    )
    to_compute = ['owner', 'filename', 'url', 'level']
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    df = file_format(query_df(stmt), compute=to_compute, level='organization')
    df[['mooring_id', 'equipment_id']] = None
    return df[c]


def select_dfiles(view=None, **kwargs):
    v = 'None' if view is None else view
    fid = None if 'file_id' not in kwargs else File.id == kwargs.get('file_id')
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'level', 'owner', 'description', 'filename', 'uploaded', 'comments',
              'path', 'url', 'organization_id', 'deployment_id', 'mooring_id', 'name',
              'equipment_id', 'mooring_equipment_id'], fid),
        'deployment.details':
            (['description', 'filename', 'name', 'uploaded', 'url'],
             Deployment.id == kwargs.get('deployment_id')),
    }
    stmt = (
        select(
            File.id, File.description, File.path, File.uploaded, File.comments,
            File.deployment_id, File.mooring_equipment_id, File.name,
            Deployment.region.label('dep_reg'), Country.name.label('dep_cou'),
            func.min(Mooring.deployed).label('dep_dat'),
            func.min(Organization.id.distinct()).label('organization_id'),
            func.string_agg(Organization.abbreviation.distinct(),
                            literal_column("','")).label('dep_org'))
        .join_from(File, Deployment)
        .outerjoin_from(Deployment, Mooring)
        .join_from(Deployment, Country)
        .join_from(Deployment, DeploymentOrganization)
        .join_from(DeploymentOrganization, Organization)
    )
    to_compute = ['owner', 'filename', 'url', 'level']
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(File, Deployment, Country)
    df = file_format(query_df(stmt), compute=to_compute, level='deployment')
    df[['mooring_id', 'equipment_id']] = None
    return df[c]


def select_mfiles(view=None, **kwargs):
    v = 'None' if view is None else view
    fid = None if 'file_id' not in kwargs else File.id == kwargs.get('file_id')
    query_def = {
        # 'view': (columns, where)
        'None':
            (['id', 'level', 'owner', 'description', 'filename', 'uploaded', 'comments',
              'path', 'url', 'organization_id', 'deployment_id', 'mooring_id', 'name',
              'equipment_id', 'mooring_equipment_id'], fid),
        'deployment.details':
            (['description', 'filename', 'uploaded', 'url', 'mooring_id', 'name'],
             Deployment.id == kwargs.get('deployment_id')),
        'mooring.details':
            (['description', 'filename', 'uploaded', 'url', 'name'],
             Mooring.id == kwargs.get('mooring_id')),
    }
    stmt = (
        select(
            File.id, File.description, File.path, File.uploaded, File.comments,
            File.name, File.mooring_equipment_id, Deployment.id.label('deployment_id'),
            func.min(Organization.id.distinct()).label('organization_id'),
            Mooring.id.label('mooring_id'), Equipment.id.label('equipment_id'),
            func.string_agg(Organization.abbreviation.distinct(),
                            literal_column("','")).label('me_org'),
            Deployment.region.label('me_reg'), Country.name.label('me_cou'),
            Mooring.deployed.label('me_dep'), Mooring.recovered.label('me_rec'),
            Mooring.latitude.label('me_lat'), Mooring.longitude.label('me_lon'))
        .join_from(File, MooringEquipment,
                   File.mooring_equipment_id == MooringEquipment.id)
        .join_from(MooringEquipment, Mooring, MooringEquipment.mooring_id == Mooring.id)
        .join_from(MooringEquipment, Equipment,
                   MooringEquipment.equipment_id == Equipment.id)
        .join_from(Mooring, Deployment, Mooring.deployment_id == Deployment.id)
        .join_from(Deployment, Country, Deployment.country_id == Country.id)
        .join_from(Deployment, DeploymentOrganization,
                   Deployment.id == DeploymentOrganization.deployment_id)
        .join_from(DeploymentOrganization, Organization,
                   DeploymentOrganization.organization_id == Organization.id)
    )
    to_compute = ['owner', 'filename', 'url', 'level']
    c, w = query_def[v]
    stmt = stmt if w is None else stmt.where(w)
    stmt = stmt.group_by(File, Deployment, Country, Mooring, Equipment)
    return file_format(query_df(stmt), compute=to_compute, level='mooring_equipment')[c]


def select_files(view=None, **kwargs):
    if view is None or view == 'file.root':
        df = pd.concat(
            [select_ufiles(), select_ofiles(), select_dfiles(), select_mfiles()]
        ).reset_index(drop=True)
        return df[['id', 'level', 'owner', 'description', 'filename', 'uploaded',
                   'url']]
    elif view == 'file.download':
        df = query_df(select(File.path, File.name).where(
            File.id == kwargs.get('file_id'))
        )
        df = file_format(df, compute=['filename'])
        return df[['path', 'filename']]
    elif view in ('file.details', 'file.edit'):
        columns = ['id', 'description', 'filename', 'path', 'uploaded', 'level',
                   'owner', 'comments']
        if view == 'file.edit':
            columns += ['organization_id', 'deployment_id', 'mooring_id',
                        'equipment_id', 'mooring_equipment_id']
        level = _get_file_level(kwargs.get('file_id'))
        if level is None:
            return pd.DataFrame(columns=columns)
        if level == 'organization':
            df = select_ofiles(**kwargs)
        elif level == 'deployment':
            df = select_dfiles(**kwargs)
        elif level == 'mooring_equipment':
            df = select_mfiles(**kwargs)
        elif level == 'unowned':
            df = select_ufiles(**kwargs)
        return df[columns]


# def select_deployment_organization(deployment_id=None, organization_id=None):
#     stmt = select(DeploymentOrganization)
#     if deployment_id is not None:
#         stmt = stmt.where(DeploymentOrganization.deployment_id == deployment_id)
#     if organization_id is not None:
#         stmt = stmt.where(DeploymentOrganization.organization_id == organization_id)
#     return query(stmt)
