from typing import Optional, Set
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped
from sqlalchemy.orm import mapped_column, relationship, validates
from flask_login import UserMixin
from datams.db.utils import connect_and_return_engine

FILE_LEVELS = ['organization', 'deployment', 'mooring_equipment', 'unowned']

# TODO: Need to make some choices on how to deal with foreign keys of deleted records
# TODO: Add validations (i.e. like constraints on what a valid timestamps is or how an
#       email address should be formatted)
# TODO: Make sure that appropriate columns are set to not null


class Base(DeclarativeBase):
    pass


# contact doesn't have to be associated to an organization
class Contact(Base):
    __tablename__ = 'Contact'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey('Organization.id', ondelete='SET NULL'), nullable=True
    )

    first_name: Mapped[str] = mapped_column(String(30))
    last_name: Mapped[str] = mapped_column(String(30))
    position: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    phone: Mapped[Optional[str]]
    avatar: Mapped[Optional[bytes]]
    comments: Mapped[Optional[str]]

    # many-to-many
    deployments: Mapped[Set['Deployment']] = relationship(
        secondary='DeploymentContact', back_populates='contacts'
    )

    # @validates("email")
    # def validate_email(self, key, address):
    #     if "@" not in address:
    #         raise ValueError("failed simple email validation")
    #     return address


class Country(Base):
    __tablename__ = 'Country'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(unique=True)
    code2: Mapped[str] = mapped_column(String(2), nullable=True)
    code3: Mapped[str] = mapped_column(String(3), nullable=True)

    # one-to-many
    deployments: Mapped[Set['Deployment']] = relationship()
    organizations: Mapped[Set['Organization']] = relationship()


# should be able to belong to no organization
class Deployment(Base):
    __tablename__ = 'Deployment'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('Country.id'))

    region: Mapped[str]
    comments: Mapped[Optional[str]]

    # one-to-many
    files: Mapped[Set['File']] = relationship()
    moorings: Mapped[Set['Mooring']] = relationship()

    # many-to-many
    organizations: Mapped[Set['Organization']] = relationship(
        secondary='DeploymentOrganization', back_populates='deployments'
    )
    contacts: Mapped[Set['Contact']] = relationship(
        secondary='DeploymentContact', back_populates='deployments'
    )


class DeletedFile(Base):
    __tablename__ = 'DeletedFile'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_id: Mapped[int]
    ftype: Mapped[str]
    organization_id: Mapped[Optional[int]]
    deployment_id: Mapped[Optional[int]]
    mooring_equipment_id: Mapped[Optional[int]]

    path: Mapped[str]
    name: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    uploaded: Mapped[int]
    deleted: Mapped[int]
    comments: Mapped[Optional[str]]


class DeploymentContact(Base):
    __tablename__ = 'DeploymentContact'

    deployment_id: Mapped[int] = mapped_column(
        ForeignKey('Deployment.id', ondelete="CASCADE"), primary_key=True
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey('Contact.id', ondelete="CASCADE"), primary_key=True
    )


class DeploymentOrganization(Base):
    __tablename__ = 'DeploymentOrganization'

    deployment_id: Mapped[int] = mapped_column(
        ForeignKey('Deployment.id', ondelete="CASCADE"), primary_key=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey('Organization.id', ondelete="CASCADE"), primary_key=True
    )


# TODO: Add condition that File can have no foreign keys or one foreign key
class File(Base):
    __tablename__ = 'File'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey('Organization.id', ondelete='SET NULL'), nullable=True
    )
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey('Deployment.id', ondelete='SET NULL'), nullable=True
    )
    mooring_equipment_id: Mapped[int] = mapped_column(
        ForeignKey('MooringEquipment.id', ondelete='SET NULL'), nullable=True
    )

    path: Mapped[str]
    name: Mapped[Optional[str]]
    description: Mapped[str]
    uploaded: Mapped[int]
    comments: Mapped[Optional[str]]


class Equipment(Base):
    __tablename__ = 'Equipment'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey('Organization.id', ondelete='SET NULL'), nullable=True
    )

    serial_number: Mapped[str] = mapped_column(unique=True)
    item: Mapped[str]
    status: Mapped[str]
    make: Mapped[Optional[str]]
    model: Mapped[Optional[str]]
    comments: Mapped[Optional[str]]

    # many-to-many
    moorings: Mapped[Set['Mooring']] = relationship(
        secondary='MooringEquipment', back_populates='equipment'
    )


class Mooring(Base):
    __tablename__ = 'Mooring'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey('Deployment.id',
                                                          ondelete='CASCADE'))
    deployed: Mapped[int]
    recovered: Mapped[Optional[int]]
    timezone: Mapped[Optional[float]]
    latitude: Mapped[Optional[float]]
    longitude: Mapped[Optional[float]]
    seafloor_depth: Mapped[Optional[float]]
    line_length: Mapped[Optional[float]]
    comments: Mapped[Optional[str]]

    # many-to-many
    equipment: Mapped['Equipment'] = relationship(
        secondary='MooringEquipment', back_populates='moorings'
    )

    # CONSTRAINT valid_timestamp CHECK (start >= 0 AND end >= 0 AND start <= end)


class MooringEquipment(Base):
    __tablename__ = 'MooringEquipment'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mooring_id: Mapped[int] = mapped_column(ForeignKey('Mooring.id',
                                                       ondelete="CASCADE"))
    equipment_id: Mapped[int] = mapped_column(ForeignKey('Equipment.id',
                                                         ondelete="CASCADE"))

    # one-to-many
    files: Mapped[Set['File']] = relationship()


class Organization(Base):
    __tablename__ = 'Organization'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_id: Mapped[int] = mapped_column(ForeignKey('Country.id'))

    name: Mapped[str] = mapped_column(unique=True)
    abbreviation: Mapped[str] = mapped_column(unique=True)
    comments: Mapped[Optional[str]]

    # one-to-many
    contacts: Mapped[Set['Contact']] = relationship()
    equipment: Mapped[Set['Equipment']] = relationship()
    files: Mapped[Set['File']] = relationship()

    # many-to-many
    deployments: Mapped[Set['Deployment']] = relationship(
        secondary='DeploymentOrganization', back_populates='organizations'
    )


# TODO: Restrict user to 0, 1, or 2 values where these represent clearance levels
#       0 is admin, 1 is editor and 2 is viewer (although only admin is being
#       used at the moment)
class User(Base, UserMixin):
    __tablename__ = 'User'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[int]  # 0 is admin, 1 is editor, 2 is viewer
    password_expired: Mapped[int]  # 0 is no, anything else is yes
    reset_key: Mapped[Optional[str]]


def wipe_db(app_config):
    engine = connect_and_return_engine(app_config)
    Base.metadata.drop_all(engine)


def initialize_db(app_config):
    engine = connect_and_return_engine(app_config)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def sync_table_models(app_config):
    engine = connect_and_return_engine(app_config)
    Base.metadata.create_all(engine)
