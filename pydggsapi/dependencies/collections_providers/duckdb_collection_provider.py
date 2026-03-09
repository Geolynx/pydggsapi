from pydggsapi.dependencies.collections_providers.abstract_collection_provider import (
    AbstractCollectionProvider,
    AbstractDatasourceInfo,
    DatetimeNotDefinedError
)
from pydggsapi.schemas.api.collection_providers import (
    CollectionProviderGetDataReturn,
    CollectionProviderGetDataDictReturn
)
from pydggsapi.schemas.api.collections import collection_timestamp_placeholder
from pydggsapi.schemas.ogc_dggs.dggrs_zones import zone_datetime_placeholder
from pydggsapi.schemas.ogc_dggs.dggrs_zones_data import Dimension, DimensionGrid
from dataclasses import dataclass, field
from datetime import datetime
from pygeofilter.ast import AstType
from pygeofilter.backends.sql import to_sql_where
from ordered_set import OrderedSet
import duckdb
import pandas as pd
import numpy as np
from typing import List, Any, Dict, Optional
import logging

logger = logging.getLogger()


@dataclass
class DuckDBDatasourceInfo(AbstractDatasourceInfo):
    # For DuckDB, we can point to a parquet file, a table name, or a query
    source: str = ""  # e.g., 'path/to/file.parquet' or 'my_table'
    is_file: bool = True
    id_col: str = ""
    conn: Optional[duckdb.DuckDBPyConnection] = None


class DuckDBCollectionProvider(AbstractCollectionProvider):
    """
    A higher performance Collection Provider using a shared DuckDB instance.
    Supports Parquet files and native DuckDB tables.
    """

    def __init__(self, datasources: Dict[str, Any]):
        self.datasources = {}
        # Support a shared database file if provided in connection settings
        db_path = ":memory:"
        if "connection" in datasources:
            db_path = datasources["connection"].get("database", ":memory:")
            # Potential other connection params like read_only can be added here
            datasources.pop("connection")

        self.con = duckdb.connect(db_path)
        self.con.install_extension("httpfs")
        self.con.load_extension("httpfs")

        for k, v in datasources.items():
            if v.get('credential') is not None:
                self.con.sql(f"CREATE OR REPLACE SECRET ({v['credential']})")
                v.pop('credential')
            
            # Initialize datasource info
            ds_info = DuckDBDatasourceInfo(**v)
            ds_info.conn = self.con
            
            if ds_info.is_file:
                # We can pre-register parquet files as views for better performance
                if ds_info.source.endswith(".parquet") or "parquet" in ds_info.source:
                    view_name = f"view_{k}"
                    self.con.sql(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{ds_info.source}')")
                    ds_info.source = view_name
            
            self.datasources[k] = ds_info

    def get_data(self, zoneIds: List[Any], res: int, datasource_id: str,
                 cql_filter: AstType = None, include_datetime: bool = False,
                 include_properties: List[str] = None,
                 exclude_properties: List[str] = None,
                 input_zoneIds_padding: bool = True,
                 collection_timestamp: datetime = None) -> CollectionProviderGetDataReturn:
        
        result = CollectionProviderGetDataReturn(zoneIds=[], cols_meta={}, data=[])
        try:
            datasource = self.datasources[datasource_id]
        except KeyError:
            logger.error(f'{__name__} {datasource_id} not found')
            raise ValueError(f'{__name__} {datasource_id} not found')

        datetime_col = datasource.datetime_col
        temporal_from_timestamp = False
        if include_datetime and datetime_col is None and collection_timestamp is not None:
            datetime_col = collection_timestamp_placeholder
            temporal_from_timestamp = True

        # Construct Column Selection
        if "*" in datasource.data_cols:
            incl = include_properties if include_properties else []
            excl = (datasource.exclude_data_cols or []) + (exclude_properties or [])
            # In DuckDB we can use SELECT * EXCLUDE(...)
            if incl:
                # If specific properties are requested, we don't use *
                cols_to_select = OrderedSet(incl)
                if not temporal_from_timestamp and datetime_col:
                    cols_to_select.add(datetime_col)
                cols_to_select.add(datasource.id_col)
                select_clause = ", ".join([f'"{c}"' for c in cols_to_select])
            else:
                exclude_str = f"EXCLUDE ({', '.join([f'\"{c}\"' for c in excl])})" if excl else ""
                select_clause = f"* {exclude_str}"
        else:
            cols_to_select = OrderedSet(datasource.data_cols)
            if include_properties:
                cols_to_select &= set(include_properties)
            if exclude_properties:
                cols_to_select -= set(exclude_properties)
            
            if not temporal_from_timestamp and datetime_col:
                cols_to_select.add(datetime_col)
            cols_to_select.add(datasource.id_col)
            select_clause = ", ".join([f'"{c}"' for c in cols_to_select])

        if temporal_from_timestamp:
            select_clause += f", CAST('{collection_timestamp}' AS TIMESTAMP) AS \"{datetime_col}\""

        # Build Query
        # We use a CTE for the input zone IDs to allow DuckDB to optimize the JOIN
        sql = f"""
        WITH input_zones AS (
            SELECT zone_id FROM (SELECT UNNEST(?) AS zone_id)
        )
        SELECT {select_clause}
        FROM "{datasource.source}" src
        JOIN input_zones ON src."{datasource.id_col}" = input_zones.zone_id
        """

        if cql_filter:
            # We need field mapping for pygeofilter
            dict_ret = self.get_datadictionary(datasource_id)
            fieldmapping = {k: k for k in dict_ret.data.keys()}
            if include_datetime:
                if datetime_col is None:
                    raise DatetimeNotDefinedError("Filter by datetime is not supported: datetime_col is None")
                fieldmapping[zone_datetime_placeholder] = datetime_col
            
            cql_sql = to_sql_where(cql_filter, fieldmapping)
            sql += f" WHERE {cql_sql}"

        # Execute and Fetch
        try:
            rel = self.con.sql(sql, params=[zoneIds])
            if input_zoneIds_padding:
                # Perform padding in DuckDB if requested
                # This is much faster than doing it in Pandas later
                input_cte = "SELECT UNNEST(?) AS zone_id_padded"
                if datetime_col:
                    # If we have temporal data, padding is more complex (needs Cartesian product with timestamps)
                    # For now, let's pull into pandas for complex temporal padding if it matches current behavior
                    # but simple padding is easy.
                    df = rel.df()
                else:
                    pad_sql = f"""
                    WITH target_ids AS (SELECT UNNEST(?) AS id),
                         data AS ({sql})
                    SELECT target_ids.id as "{datasource.id_col}", data.* EXCLUDE ("{datasource.id_col}")
                    FROM target_ids
                    LEFT JOIN data ON target_ids.id = data."{datasource.id_col}"
                    """
                    df = self.con.sql(pad_sql, params=[zoneIds, zoneIds]).df()
            else:
                df = rel.df()
        except Exception as e:
            logger.error(f'DuckDB Query Error: {e}')
            return result

        if df.empty:
            return result

        # Metadata extraction
        cols_meta = {k: v.name for k, v in dict(df.dtypes).items() if k != datasource.id_col}
        
        # Temporal handling
        cols_dims = None
        zone_dates = None
        if datetime_col and datetime_col in df.columns:
            if np.issubdtype(df[datetime_col].dtype, np.datetime64):
                df[datetime_col] = df[datetime_col].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            unique_dates = sorted(df[datetime_col].unique())
            cols_dims = [
                Dimension(
                    name=datetime_col,
                    interval=[str(unique_dates[0]), str(unique_dates[-1])],
                    grid=DimensionGrid(
                        cellsCount=len(unique_dates),
                        coordinates=[str(d) for d in unique_dates],
                    )
                )
            ]
            zone_dates = df[datetime_col].astype(str).tolist()
            cols_meta.pop(datetime_col, None)
            df = df.drop(columns=[datetime_col])

        result_ids = df[datasource.id_col].tolist()
        data_values = df.drop(columns=[datasource.id_col]).values.tolist()
        
        result.zoneIds = result_ids
        result.cols_meta = cols_meta
        result.data = data_values
        result.datetimes = zone_dates
        result.dimensions = cols_dims
        
        return result

    def get_datadictionary(self, datasource_id: str, include_zone_id: bool = True) -> CollectionProviderGetDataDictReturn:
        try:
            datasource = self.datasources[datasource_id]
        except KeyError:
            raise ValueError(f"Datasource {datasource_id} not found")
        
        res = self.con.sql(f"SELECT * FROM \"{datasource.source}\" LIMIT 0")
        df = res.df()
        
        data = {}
        for col, dtype in zip(df.columns, res.types):
            if not include_zone_id and col == datasource.id_col:
                continue
            # Map DuckDB types to simple strings
            data[col] = str(dtype).lower()
            
        return CollectionProviderGetDataDictReturn(data=data)
