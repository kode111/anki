# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import anki

# DBValue is actually Union[str, int, float, None], but if defined
# that way, every call site needs to do a type check prior to using
# the return values.
ValueFromDB = Any
Row = Sequence[ValueFromDB]

ValueForDB = Union[str, int, float, None]


class DBProxy:
    # Lifecycle
    ###############

    def __init__(self, backend: anki.rsbackend.RustBackend, path: str) -> None:
        self._backend = backend
        self._path = path
        self.mod = False

    # Transactions
    ###############

    def begin(self) -> None:
        self._backend.db_begin()

    def commit(self) -> None:
        self._backend.db_commit()

    def rollback(self) -> None:
        self._backend.db_rollback()

    # Querying
    ################

    def _query(
        self, sql: str, *args: ValueForDB, first_row_only: bool = False, **kwargs
    ) -> List[Row]:
        # mark modified?
        s = sql.strip().lower()
        for stmt in "insert", "update", "delete":
            if s.startswith(stmt):
                self.mod = True
        sql, args2 = emulate_named_args(sql, args, kwargs)
        # fetch rows
        return self._backend.db_query(sql, args2, first_row_only)

    # Query shortcuts
    ###################

    def all(self, sql: str, *args: ValueForDB, **kwargs) -> List[Row]:
        return self._query(sql, *args, **kwargs)

    def list(self, sql: str, *args: ValueForDB, **kwargs) -> List[ValueFromDB]:
        return [x[0] for x in self._query(sql, *args, **kwargs)]

    def first(self, sql: str, *args: ValueForDB, **kwargs) -> Optional[Row]:
        rows = self._query(sql, *args, first_row_only=True, **kwargs)
        if rows:
            return rows[0]
        else:
            return None

    def scalar(self, sql: str, *args: ValueForDB, **kwargs) -> ValueFromDB:
        rows = self._query(sql, *args, first_row_only=True, **kwargs)
        if rows:
            return rows[0][0]
        else:
            return None

    # execute used to return a pysqlite cursor, but now is synonymous
    # with .all()
    execute = all

    # Updates
    ################

    def executemany(self, sql: str, args: Iterable[Sequence[ValueForDB]]) -> None:
        self.mod = True
        if isinstance(args, list):
            list_args = args
        else:
            list_args = list(args)
        self._backend.db_execute_many(sql, list_args)


# convert kwargs to list format
def emulate_named_args(
    sql: str, args: Tuple, kwargs: Dict[str, Any]
) -> Tuple[str, Sequence[ValueForDB]]:
    # nothing to do?
    if not kwargs:
        return sql, args
    print("named arguments in queries will go away in the future:", sql)
    # map args to numbers
    arg_num = {}
    args2 = list(args)
    for key, val in kwargs.items():
        args2.append(val)
        n = len(args2)
        arg_num[key] = n
    # update refs
    def repl(m):
        arg = m.group(1)
        return f"?{arg_num[arg]}"

    sql = re.sub(":([a-zA-Z_0-9]+)", repl, sql)
    return sql, args2
