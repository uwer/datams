import pandas as pd
import click
from flask import current_app, g
from sqlalchemy.orm import Session

from datams.db.utils import (conect_and_return_engine, initialize_db,
                             sync_table_models, create_upload_directories,
                             validate_discovery_directory, result_to_df)


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
    return result_to_df(query(statement))


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
        return conect_and_return_engine()


@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    r = input('\nWARNING: This action will reset the database tables removing any and '
              'all stored values!  Do you want to continue? Y or [N]: ')
    if r.lower() == 'y':
        initialize_db()
        click.echo('\nInitialized the database.')
    else:
        click.echo('\nInitialization aborted.')


def database_init_app(app):
    # create the upload directories
    create_upload_directories(app.config['DATA_FILES']['upload_directory'])

    # validate the discovery directory
    validate_discovery_directory(app.config['DATA_FILES']['upload_directory'])

    # create the engine to the database
    app.extensions['sqlalchemy_engine'] = conect_and_return_engine()

    # ensure that the sqlalchemy orm models match the database
    sync_table_models()

    app.cli.add_command(init_db_command)  # register the init-db command
    # TODO: app.teardown_appcontext(close_engine)?
