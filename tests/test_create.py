import os
import pytest

import sqlalchemy as sa
from sqlalchemy import create_engine

from sqlalchemy_doris import datatype
from sqlalchemy_doris import HASH, RANGE


@pytest.fixture
def doris_engine():
    host = os.environ['DORIS_HOST']
    user = os.environ['DORIS_USER']
    password = os.environ['DORIS_PASSWORD']
    port = os.environ['DORIS_PORT']
    database = os.environ['DORIS_DATABASE']

    engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

    return engine


def test_create_table(doris_engine):
    metadata_obj = sa.MetaData()
    table_obj = sa.Table(
        'test_table',
        metadata_obj,
        sa.Column("id", datatype.Integer),
        doris_unique_key=('id', ),
        doris_partition_by=RANGE('id'),
        doris_distributed_by=HASH('id'),
        doris_properties={"replication_allocation": "tag.location.default: 1"}
    )

    metadata_obj.create_all(doris_engine)

    metadata_obj.drop_all(doris_engine, [table_obj])
