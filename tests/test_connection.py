import os

from sqlalchemy import create_engine


def test_connect():

    host = os.environ['DORIS_HOST']
    user = os.environ['DORIS_USER']
    password = os.environ['DORIS_PASSWORD']
    port = os.environ['DORIS_PORT']
    database = os.environ['DORIS_DATABASE']

    engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

    with engine.connect() as conn:
        pass
