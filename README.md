# Apache Doris Dialect for SQLAlchemy

This is an unofficial implementation forked from [pydoris](https://pypi.org/project/pydoris/1.0.1/)

## Features
* support SQLAlchemy 2.
* support pymysql and mysqlclient as driver.

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
