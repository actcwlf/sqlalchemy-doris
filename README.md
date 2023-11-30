# Apache Doris Dialect for SQLAlchemy

This is an unofficial implementation forked from [pydoris](https://pypi.org/project/pydoris/1.0.1/)

## Features
* support SQLAlchemy 2.
* support pymysql and mysqlclient as driver.
* support SQLAlchemy table creation

## Installation
Use
```bash
pip install sqlalchemy-doris[pymysql]
```
for pymysql.

Or

```bash
pip install sqlalchemy-doris[mysqldb]
```
for mysqlclient.

Note sqlalchemy-doris uses pymysql as default connector for compatibility. 
If both pymysql and mysqlclient are installed, mysqlclient is preferred.


## Usage
```python

from sqlalchemy import create_engine

engine = create_engine(f"doris+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")
# or
engine = create_engine(f"doris+mysqldb://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")

```

### Create Table
```python
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy_doris import datatype
from sqlalchemy_doris import HASH, RANGE

engine = create_engine(f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4")


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

metadata_obj.create_all(engine)

```

SQL is
```sql
CREATE TABLE test_table (
	id INTEGER
)
UNIQUE KEY (`id`)
PARTITION BY RANGE(`id`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS auto
PROPERTIES (
    "replication_allocation" = "tag.location.default: 1"
)
```
