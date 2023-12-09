import os
import click
import re
from pathlib import Path
import pandas as pd

from sqlalchemy import select, update, delete, insert
from datams.utils import (APP_CONFIG, PROCESSED_DIRECTORY, DISCOVERY_DIRECTORY,
                          ALLOWED_CHARACTERS)
from datams.db.core import query_df, query_all
from datams.db.tables import File, User, wipe_db, initialize_db
from werkzeug.security import generate_password_hash
# from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError

# .errors.UniqueViolation

@click.command('wipe-db')
def wipe_db_command():
    """Clear all the existing data and tables."""
    r = input('\nWARNING: This action will remove all database tables and all stored '
              'values!  Do you want to continue? Y or [N]: ')
    if r.lower() == 'y':
        wipe_db(APP_CONFIG)
        click.echo('\nDatabase wiped.')
    else:
        click.echo('\nWipe operation aborted.')


@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    r = input('\nWARNING: This action will reset the database tables removing any and '
              'all stored values!  Do you want to continue? Y or [N]: ')
    if r.lower() == 'y':
        initialize_db(APP_CONFIG)
        click.echo('\nInitialized the database.')
    else:
        click.echo('\nInitialization aborted.')


@click.command('resolve-files')
def resolve_files_command():
    """
    Attempts to find all the file resources it can within the upload or discovery
    directories.  Anything it can't find is dropped from the database.
    """
    r = input('\nWARNING: This action will remove database entries for file resources '
              'it is unable to uniquely resolve.  This script will first check if the '
              'path to the file resource exists.  If not it searches through the '
              'uploads and discovery directories looking for a single exact basename '
              'match. If none or multiple matches are found it is dropped!  '
              'Do you want to continue? Y or [N]: ')
    if r.lower() == 'y':
        # 1. build the map of what files are present
        fmap = {}
        for f in Path(PROCESSED_DIRECTORY).rglob('*'):
            if f.is_file():
                path = os.path.realpath(str(f))
                filename = os.path.basename(path)
                if filename in fmap.keys():
                    fmap.pop(filename)  # ignore when multiple
                else:
                    fmap[filename] = path
        for f in Path(DISCOVERY_DIRECTORY).rglob('*'):
            if f.is_file():
                path = os.path.realpath(str(f))
                filename = os.path.basename(path)
                if filename in fmap.keys():
                    fmap.pop(filename)  # ignore when multiple
                else:
                    fmap[filename] = path

        # 2. get all the files from database
        df = query_df(select(File.id, File.path))
        all_ids = list(df['id'])

        df['exists'] = df['path'].apply(lambda x: os.path.exists(x))
        df['filename'] = df['path'].apply(lambda x: os.path.basename(x))

        # 3. get indexes of good entries (these are good because their paths exist)
        df_good = pd.DataFrame(columns=['id'])
        df_good['id'] = df.loc[df['exists'], 'id']

        # 4. get indexes and filenames of ones to be checked
        df = df.loc[~df['exists'],
                    ['id', 'filename']].drop_duplicates(subset=['filename'])

        # 5. get the new path or None if can't resolve
        df['path'] = df['filename'].apply(lambda x: fmap.get(x))

        # 6. drop the entries that are None/na
        df_rename = df.dropna()

        # 7. get the indexes that should be dropped
        to_drop = (
            set(all_ids)
            .difference(list(df_good['id']))
            .difference(list(df_rename['id']))
        )
        # 7. create the two queries:
        #       drop the indexes that couldn't be resolved
        #       update the paths of the ones that could
        query_all(
            [delete(File).where(File.id.in_(to_drop))] +
            [update(File).values(path=row['path']).where(File.id == row['id'])
             for idx, row in df_rename.iterrows()]
        )
        click.echo('\nFilenames resolved.')
    else:
        click.echo('\nFilename resolution aborted.')


@click.command('create-user')
@click.argument('username', nargs=1)
@click.option('--email', prompt=True)
@click.option('--admin', is_flag=True, show_default=True, default=False,
              help="Set to create admin user")
@click.password_option()
def create_user_command(username: str, email: str, admin: bool, password: str):
    # 1. check that username only uses ALLOWED_CHARACTERS
    if not set(username).issubset(ALLOWED_CHARACTERS):
        msg = (f"\n\nFailed to create user: `{username}`:\n    Usernames may only "
               f"contain letters, numbers, dashes and underscores.  \n")
        print(msg)
        return

    # 2. check that email matches the regular expression of an email form
    if not re.match('^\S+@\S+\.\S+$', email):
        msg = (f"\n\nFailed to create user: `{username}`:\n    Email address: "
               f"`{email}` is invalid.  \n")
        print(msg)
        return

    # 3. check that password is at least 6 characters
    if len(password) < 6:
        msg = (f"\n\nFailed to create user: `{username}`:\n    Password must be at "
               f"least 6 characters.  \n")
        print(msg)
        return

    role = 0 if admin else 1
    email = email.lower()
    password = generate_password_hash(password)
    stmt = insert(User).values(
        username=username, email=email, password=password, role=role, password_expired=1
    )
    try:
        query_all([stmt])
    except IntegrityError:
        msg = f"\n\nFailed to create user: `{username}`:  \n"
        df1 = query_df(select(User.id).where(User.username == username))
        df2 = query_df(select(User.id).where(User.email == email))
        if df1.shape[0] > 0:
            msg += f"    Username: `{username}` is already taken.  \n"
        if df2.shape[0] > 0:
            msg += f"    Email: `{email}` is already taken.  \n"
        print(msg)
        return

    print(f"\nSuccessfully created user: `{username}`")


@click.command('delete-user')
@click.argument('username', nargs=1)
def delete_user_command(username: str):
    df = query_df(select(User.id).where(User.username == username))
    if df.shape[0] == 0:
        print(f"\nNo user found with username: `{username}`")
        return
    else:
        stmt = delete(User).where(User.username == username)
        try:
            query_all([stmt])
        except IntegrityError as error:
            print(error)
            return
        print(f"\nSuccessfully deleted user: `{username}`")