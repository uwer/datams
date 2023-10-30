from typing import Any, Dict
from sqlalchemy import insert
from datams.db.core import query_all
from datams.db.tables import (Contact, Deployment, DeploymentOrganization, File,
                              Mooring, Organization, Equipment)


def insert_query(table, values):
    if table == 'Contact':
        insert_contact(values)
    elif table == 'Deployment':
        insert_deployment(values)
    elif table == 'Equipment':
        insert_equipment(values)
    elif table == 'File':
        insert_files(values)
    elif table == 'Mooring':
        insert_mooring(values)
    elif table == 'Organization':
        insert_organization(values)
    else:
        raise NotImplementedError


def insert_contact(values: Dict[str, Any]):
    query_all([insert(Contact).values(**values)])


def insert_deployment(values: Dict[str, Any]):
    deployment_id = values['id']
    organization_ids = values.pop('organization_ids')
    query_all([insert(Deployment).values(**values)])
    query_all([insert(DeploymentOrganization)
               .values(deployment_id=deployment_id, organization_id=organization_id)
               for organization_id in organization_ids])


def insert_files(values: Dict[str, Any]):
    paths = values.pop('paths')
    query_all([insert(File).values(path=p, **values) for p in paths])


def insert_equipment(values: Dict[str, Any]):
    query_all([insert(Equipment).values(**values)])


def insert_mooring(values: Dict[str, Any]):
    query_all([insert(Mooring).values(**values)])


def insert_organization(values: Dict[str, Any]):
    query_all([insert(Organization).values(**values)])


def insert_deployment_contact():
    pass


def insert_deployment_organization():
    pass


def insert_mooring_equipment():
    pass


