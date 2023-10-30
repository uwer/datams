from sqlalchemy import delete, select
from datams.db.core import query_all, query_first
from datams.db.tables import (Contact, Deployment, File, Mooring, Organization,
                              Equipment)


def delete_query(table, **kwargs):
    if table == 'Contact':
        delete_contact(kwargs['contact_id'])
    elif table == 'Deployment':
        delete_deployment(kwargs['deployment_id'])
    elif table == 'Equipment':
        delete_equipment(kwargs['equipment_id'])
    elif table == 'File':
        delete_file(kwargs['file_id'])
    elif table == 'Mooring':
        delete_mooring(kwargs['mooring_id'])
    elif table == 'Organization':
        delete_organization(kwargs['organization_id'])
    else:
        raise NotImplementedError


def delete_contact(contact_id):
    query_all([delete(Contact).where(Contact.id == contact_id)])


def delete_deployment(deployment_id):
    query_all([delete(Deployment).where(Deployment.id == deployment_id)])


def delete_file(file_id):
    query_all([delete(File).where(File.id == file_id)])


def delete_equipment(equipment_id):
    query_all([delete(Equipment).where(Equipment.id == equipment_id)])


def delete_mooring(mooring_id):
    query_all([delete(Mooring).where(Mooring.id == mooring_id)])


def delete_organization(organization_id):
    query_all([delete(Organization).where(Organization.id == organization_id)])
