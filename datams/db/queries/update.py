from typing import Any, Dict
from sqlalchemy import insert, update, delete
from datams.db.core import query_all
from datams.db.tables import (Contact, Deployment, File, Mooring, Organization,
                              Equipment, DeploymentOrganization, DeploymentContact,
                              MooringEquipment)


def update_query(table, values, **kwargs):
    if table == 'Contact':
        update_contact(kwargs['contact_id'], values)
    elif table == 'Deployment':
        update_deployment(kwargs['deployment_id'], values)
    elif table == 'Equipment':
        update_equipment(kwargs['equipment_id'], values)
    elif table == 'File':
        update_file(kwargs['file_id'], values)
    elif table == 'Mooring':
        update_mooring(kwargs['mooring_id'], values)
    elif table == 'Organization':
        update_organization(kwargs['organization_id'], values)
    else:
        raise NotImplementedError


def update_contact(contact_id, values: Dict[str, Any]):
    query_all([update(Contact).values(**values).where(Contact.id == contact_id)])


def update_deployment(deployment_id, values: Dict[str, Any]):
    # updated associated deployments
    contact_ids = values.pop('contact_ids')
    # remove existing
    query_all([delete(DeploymentContact)
              .where(DeploymentContact.deployment_id == deployment_id)])
    # add new
    query_all([insert(DeploymentContact)
              .values(deployment_id=deployment_id, contact_id=contact_id)
               for contact_id in contact_ids])

    organization_ids = values.pop('organization_ids')
    # remove existing
    query_all([delete(DeploymentOrganization)
              .where(DeploymentOrganization.deployment_id == deployment_id)])
    # add new
    query_all([
        insert(DeploymentOrganization)
        .values(deployment_id=deployment_id, organization_id=organization_id)
        for organization_id in organization_ids
    ])

    # update the deployment information
    query_all(
        [update(Deployment).values(**values).where(Deployment.id == deployment_id)])


# def update_file_orig(file_id, values):
#     query_all([update(File).values(**values).where(File.id == file_id)])


def update_files(values):
    indexes = values.pop('indexes')
    query_all([update(File).values(**values).where(File.id.in_(indexes))])


def update_equipment(equipment_id, values: Dict[str, Any]):
    query_all([update(Equipment).values(**values).where(Equipment.id == equipment_id)])


def update_mooring(mooring_id, values: Dict[str, Any]):
    equipment_ids = values.pop('equipment_ids')
    # remove existing
    query_all([delete(MooringEquipment)
              .where(MooringEquipment.mooring_id == mooring_id)])
    # add new
    query_all([insert(MooringEquipment)
              .values(mooring_id=mooring_id, equipment_id=equipment_id)
               for equipment_id in equipment_ids])

    query_all([update(Mooring).values(**values).where(Mooring.id == mooring_id)])


def update_organization(organization_id, values: Dict[str, Any]):
    # update associated contacts
    contact_ids = values.pop('contact_ids')
    # remove existing
    query_all([update(Contact).values(organization_id=None)
              .where(Contact.organization_id == organization_id)])
    # add new
    query_all([update(Contact).values(organization_id=organization_id)
              .where(Contact.id.in_(contact_ids))])

    # updated associated deployments
    deployment_ids = values.pop('deployment_ids')
    query_all([delete(DeploymentOrganization)
              .where(DeploymentOrganization.organization_id == organization_id)])
    # add new
    query_all([insert(DeploymentOrganization)
               .values(deployment_id=deployment_id, organization_id=organization_id)
               for deployment_id in deployment_ids])

    equipment_ids = values.pop('equipment_ids')
    # remove existing
    query_all([update(Equipment).values(organization_id=None)
              .where(Equipment.organization_id == organization_id)])
    # add new
    query_all([update(Equipment).values(organization_id=organization_id)
              .where(Equipment.id.in_(equipment_ids))])

    # update organization
    query_all([update(Organization)
              .values(**values)
              .where(Organization.id == organization_id)])
