import pandas as pd
import click
from flask import current_app, g
from sqlalchemy import select
from sqlalchemy.orm import Session
from datams.utils import APP_CONFIG
from datams.db.utils import (connect_and_return_engine, create_upload_directories,
                             validate_discovery_directory)
from datams.db.tables import wipe_db, initialize_db, sync_table_models

from datams.db.tables import File
from datams.utils import PROCESSED_DIRECTORY, DISCOVERY_DIRECTORY
from pathlib import Path
import os
from sqlalchemy import update, delete


def query(statement):
    """
    get query results unaltered
    """
    engine = get_engine()
    with Session(engine) as session:
        result = session.execute(statement)
    return result


def query_first(statement):
    """
    get first result of query or None if no results
    """
    engine = get_engine()
    with Session(engine) as session:
        result = session.execute(statement).first()
    return result if result is None else result[0]


def query_df(statement):
    """
    return query results as a dataframe empty dataframe if None
    """
    engine = get_engine()
    with Session(engine) as session:
        result = session.execute(statement)
        df = pd.DataFrame(result, columns=result.keys())
    return df


def query_all(statements: list) -> None:
    engine = get_engine()
    with Session(engine) as session:
        for statement in statements:
            session.execute(statement)
        session.commit()
    return


def query_first_df(statement):
    """
    return query results as a series empty series if None
    """
    df = query_df(statement)
    if df.empty:
        return pd.Series(index=df.columns)
    return df.iloc[0]


def get_engine(app=None):
    try:
        if app is None:
            if 'engine' not in g:
                g.engine = current_app.extensions['sqlalchemy_engine']
            return g.engine
        else:
            return app.extensions['sqlalchemy_engine']
    except RuntimeError:
        return connect_and_return_engine(APP_CONFIG)


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


def add_user_command():
    pass


def database_init_app(app):
    # create the upload directories
    create_upload_directories(app.config['DATA_FILES']['upload_directory'])

    # validate the discovery directory
    validate_discovery_directory(app.config['DATA_FILES']['upload_directory'])

    # create the engine to the database
    app.extensions['sqlalchemy_engine'] = connect_and_return_engine(APP_CONFIG)

    # ensure that the sqlalchemy orm models match the database
    sync_table_models(APP_CONFIG)

    app.cli.add_command(wipe_db_command)  # register the wipe-db command
    app.cli.add_command(init_db_command)  # register the init-db command
    app.cli.add_command(resolve_files_command)  # ...
    # TODO: app.teardown_appcontext(close_engine)?
