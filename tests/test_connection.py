import os

from sqlalchemy import create_engine
from sqlalchemy_doris import registry


def test_connect():
    print(registry)
    host = os.environ['DORIS_HOST']
    user = os.environ['DORIS_USER']
    password = os.environ['DORIS_PASSWORD']
    port = os.environ['DORIS_PORT']
    database = os.environ['DORIS_DATABASE']

    engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
    assert engine.driver == 'mysqldb'
    with engine.connect() as conn:
        pass

    engine = create_engine(f"doris+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
    assert engine.driver == 'pymysql'

    with engine.connect() as conn:
        pass
    #
    engine = create_engine(f"doris+mysqldb://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
    assert engine.driver == 'mysqldb'

    with engine.connect() as conn:
        pass
