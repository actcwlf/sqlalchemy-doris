#! /usr/bin/python3

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import logging
from typing import Any, Dict, List
from sqlalchemy import log, exc, text
from sqlalchemy.dialects.mysql.base import MySQLCompiler, MySQLDDLCompiler
from sqlalchemy.dialects.mysql import reflection as _reflection
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql
from sqlalchemy.engine import Connection
from sqlalchemy.util import topological

from sqlalchemy_doris import datatype
from sqlalchemy.sql import elements, operators, functions, sqltypes
from sqlalchemy.schema import CreateTable


logger = logging.getLogger(__name__)


def join_args_with_quote(*args):
    args = [f'`{a}`' for a in args]
    args_str = ', '.join(args)
    return '(' + args_str + ')'


def format_properties(**kwargs):
    entries = []
    for k, v in kwargs.items():
        entry = f'"{k}" = "{v}",'
        entries.append(entry)
    result_str = '\n    '.join(entries)
    return '(\n    ' + result_str[:-1] + '\n)'


class HASH:
    def __init__(self, *keys: [str], buckets='auto'):
        self.keys = keys
        self.buckets = buckets

    def render(self):
        keys_str = 'HASH' + join_args_with_quote(*self.keys)
        buckets_str = f'BUCKETS {self.buckets}'
        return keys_str + ' ' + buckets_str


class RANGE:
    def __init__(self, *keys: [str], part_info=tuple()):
        self.keys = keys
        self.part_info = part_info

    def render(self):
        keys_str = 'RANGE' + join_args_with_quote(*self.keys)
        if len(self.part_info) > 0:
            part_str = ',\n    '.join(self.part_info)
            part_str = '(\n    ' + part_str + '\n)'
        else:
            part_str = '()'
        return keys_str + ' ' + part_str


class RANDOM(HASH):
    def render(self):
        keys_str = 'RANDOM' + join_args_with_quote(*self.keys)
        buckets_str = f'BUCKETS {self.buckets}'
        return keys_str + ' ' + buckets_str


class DorisDDLCompiler(MySQLDDLCompiler):
    def visit_create_table(self, create, **kw):
        table = create.element
        preparer = self.preparer

        text = "\nCREATE "
        if table._prefixes:
            text += " ".join(table._prefixes) + " "

        text += "TABLE "
        if create.if_not_exists:
            text += "IF NOT EXISTS "

        text += preparer.format_table(table) + " "

        create_table_suffix = self.create_table_suffix(table)
        if create_table_suffix:
            text += create_table_suffix + " "

        text += "("

        separator = "\n"

        # if only one primary key, specify it along with the column
        # first_pk = False primary key is not supported
        for create_column in create.columns:
            column = create_column.element
            assert column.primary_key is False
            try:
                processed = self.process(create_column)
                if processed is not None:
                    text += separator
                    separator = ", \n"
                    text += "\t" + processed
                if column.primary_key:
                    first_pk = True
            except exc.CompileError as ce:
                raise exc.CompileError(
                    "(in table '%s', column '%s'): %s"
                    % (table.description, column.name, ce.args[0])
                ) from ce

        # constraint is not supported
        # const = self.create_table_constraints(
        #     table,
        #     _include_foreign_key_constraints=create.include_foreign_key_constraints,  # noqa
        # )
        # if const:
        #     text += separator + "\t" + const

        text += "\n)\n%s\n\n" % self.post_create_table(table)
        return text



    def post_create_table(self, table):
        """Build table-level CREATE options like ENGINE and COLLATE."""

        table_opts = []

        # opts = {
        #     k[len(self.dialect.name) + 1 :].upper(): v
        #     for k, v in table.kwargs.items()
        #     if k.startswith("%s_" % self.dialect.name)
        # }

        opts = {}
        for k, v in table.kwargs.items():
            if k.startswith("%s_" % self.dialect.name):
                opts[k[len(self.dialect.name) + 1:].upper()] = v

        if table.comment is not None:
            opts["COMMENT"] = table.comment

        # partition_options = [
        #     # "PARTITION_BY",
        #     # "PARTITIONS",
        #     # "SUBPARTITIONS",
        #     # "SUBPARTITION_BY",
        #     "DISTRIBUTED_BY"
        # ]
        #
        # nonpart_options = set(opts).difference(partition_options)
        # part_options = set(opts).intersection(partition_options)


        for opt in topological.sort(
            [
                ("UNIQUE_KEY", "PARTITION_BY"),
                ("AGGREGATE_KEY", "PARTITION_BY"),
                ("DUPLICATE_KEY", "PARTITION_BY"),
                ("UNIQUE_KEY",    "DISTRIBUTED_BY"),
                ("AGGREGATE_KEY", "DISTRIBUTED_BY"),
                ("DUPLICATE_KEY", "DISTRIBUTED_BY"),
                ("PARTITION_BY", "DISTRIBUTED_BY"),
                ("DISTRIBUTED_BY", "PROPERTIES")
            ],
            opts,
        ):
            arg = opts[opt]
            if opt in _reflection._options_of_type_string:
                arg = self.sql_compiler.render_literal_value(
                    arg, sqltypes.String()
                )

            opt = opt.replace("_", " ")

            if opt in (
                "UNIQUE KEY",
                "AGGREGATE KEY",
                "DUPLICATE KEY",
            ):
                if isinstance(arg, str):
                    arg = join_args_with_quote(arg)
                else:
                    assert isinstance(arg, tuple)
                    arg = join_args_with_quote(*arg)

            if opt == "PARTITION BY":
                arg = arg.render()

            if opt == 'DISTRIBUTED BY':
                assert isinstance(arg, HASH) or isinstance(arg, RANDOM)
                arg = arg.render()

            if opt == 'PROPERTIES':
                arg = format_properties(**arg)

            joiner = " "
            table_opts.append(joiner.join((opt, arg)))


        return "\n".join(table_opts)


@log.class_logger
class DorisDialectMixin(DefaultDialect):
    # Caching
    # Warnings are generated by SQLAlchmey if this flag is not explicitly set
    # and tests are needed before being enabled
    supports_statement_cache = False


    name = 'doris'

    def __init__(self, *args, **kw):
        super(DorisDialectMixin, self).__init__(*args, **kw)

    def has_table(self, connection, table_name, schema=None, **kw):
        self._ensure_has_table_connection(connection)

        if schema is None:
            schema = self.default_schema_name

        assert schema is not None

        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(
                schema, table_name
            )
        )

        # DESCRIBE *must* be used because there is no information schema
        # table that returns information on temp tables that is consistently
        # available on MariaDB / MySQL / engine-agnostic etc.
        # therefore we have no choice but to use DESCRIBE and an error catch
        # to detect "False".  See issue #9058

        try:
            with connection.exec_driver_sql(
                f"DESCRIBE {full_name}",
                execution_options={"skip_user_error_events": True},
            ) as rs:
                return rs.fetchone() is not None
        except exc.DBAPIError as e:
            # https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html  # noqa: E501
            # there are a lot of codes that *may* pop up here at some point
            # but we continue to be fairly conservative.  We include:
            # 1146: Table '%s.%s' doesn't exist - what every MySQL has emitted
            # for decades
            #
            # mysql 8 suddenly started emitting:
            # 1049: Unknown database '%s'  - for nonexistent schema
            #
            # also added:
            # 1051: Unknown table '%s' - not known to emit
            #
            # there's more "doesn't exist" kinds of messages but they are
            # less clear if mysql 8 would suddenly start using one of those
            # print('caught exception', e)
            if self._extract_error_code(e.orig) in (1105, 1051):
                info: str = e.orig.args[1].split('detailMessage = ')[-1]
                if info.startswith('Unknown table'):
                    return False
            raise


    def get_schema_names(self, connection, **kw):
        rp = connection.exec_driver_sql("SHOW schemas")
        return [r[0] for r in rp]

    def get_table_names(self, connection, schema=None, **kw):
        """Return a Unicode SHOW TABLES from a given schema."""
        if schema is not None:
            current_schema = schema
        else:
            current_schema = self.default_schema_name

        charset = self._connection_charset

        rp = connection.exec_driver_sql(
            "SHOW FULL TABLES FROM %s"
            % self.identifier_preparer.quote_identifier(current_schema)
        )

        return [
            row[0]
            for row in self._compat_fetchall(rp, charset=charset)
        ]

    def get_view_names(self, connection, schema=None, **kw):
        if schema is None:
            schema = self.default_schema_name
        charset = self._connection_charset
        rp = connection.exec_driver_sql(
            "SHOW FULL TABLES FROM %s"
            % self.identifier_preparer.quote_identifier(schema)
        )
        return [
            row[0]
            for row in self._compat_fetchall(rp, charset=charset)
            if row[1] in ("VIEW", "SYSTEM VIEW")
        ]

    def get_columns(self, connection: Connection, table_name: str, schema: str = None, **kw) -> List[Dict[str, Any]]:
        if not self.has_table(connection, table_name, schema):
            raise exc.NoSuchTableError(f"schema={schema}, table={table_name}")
        schema = schema or self._get_default_schema_name(connection)

        quote = self.identifier_preparer.quote_identifier
        full_name = quote(table_name)
        if schema:
            full_name = "{}.{}".format(quote(schema), full_name)

        res = connection.execute(text(f"SHOW COLUMNS FROM {full_name}"))
        columns = []
        for record in res:
            column = dict(
                name=record.Field,
                type=datatype.parse_sqltype(record.Type),
                nullable=record.Null == "YES",
                default=record.Default,
            )
            columns.append(column)
        return columns


    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        return {  # type: ignore  # pep-655 not supported
            "name": None,
            "constrained_columns": [],
        }

    def get_unique_constraints(
            self, connection: Connection, table_name: str, schema: str = None, **kw
    ) -> List[Dict[str, Any]]:
        return []

    def get_check_constraints(
            self, connection: Connection, table_name: str, schema: str = None, **kw
    ) -> List[Dict[str, Any]]:
        return []

    def get_foreign_keys(
            self, connection: Connection, table_name: str, schema: str = None, **kw
    ) -> List[Dict[str, Any]]:
        return []

    def get_primary_keys(self, connection: Connection, table_name: str, schema: str = None, **kw) -> List[str]:
        pk = self.get_pk_constraint(connection, table_name, schema)
        return pk.get("constrained_columns")  # type: ignore

    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []

    def has_sequence(self, connection: Connection, sequence_name: str, schema: str = None, **kw) -> bool:
        return False

    def get_sequence_names(self, connection: Connection, schema: str = None, **kw) -> List[str]:
        return []

    def get_temp_view_names(self, connection: Connection, schema: str = None, **kw) -> List[str]:
        return []

    def get_temp_table_names(self, connection: Connection, schema: str = None, **kw) -> List[str]:
        return []

    def get_table_options(self, connection, table_name, schema=None, **kw):
        return {}

    def get_table_comment(self, connection: Connection, table_name: str, schema: str = None, **kw) -> Dict[str, Any]:
        return dict(text=None)


class DorisDialect_pymysql(DorisDialectMixin, MySQLDialect_pymysql):
    supports_statement_cache = False
    ddl_compiler = DorisDDLCompiler


class DorisDialect_mysqldb(DorisDialectMixin, MySQLDialect_mysqldb):
    supports_statement_cache = False
    ddl_compiler = DorisDDLCompiler


try:
    # using MySQLdb as default driver if available
    import MySQLdb
    DorisDialect = DorisDialect_mysqldb

except ModuleNotFoundError:
    DorisDialect = DorisDialect_pymysql
