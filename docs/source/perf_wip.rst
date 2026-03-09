Performance and Architectural Improvements (WIP)
===========================================

This document outlines the recent experimental improvements made to the ``pydggsapi`` architecture, specifically targeting higher throughput and leaner deployments on small servers.

DuckDB Collection Provider
--------------------------

A new ``DuckDBCollectionProvider`` has been introduced to replace or augment the standard Parquet provider. 

**Key Features:**
* **Native SQL Execution:** Unlike the standard provider which pulls data into Pandas for merging, this provider pushes JOIN operations and filters directly into DuckDB's vectorized C++ engine.
* **Persistent Views:** Parquet files are registered as persistent ``VIEW`` objects during initialization. This allows DuckDB to reuse metadata and statistics, significantly reducing "cold-start" latency for requests.
* **Optimized Padding:** Data alignment and NaN-padding for missing zones are performed in SQL, reducing the amount of data transferred between the database and Python.

**Configuration Example:**

.. code-block:: json

   "collection_providers": {
     "duckdb_high_perf": {
       "classname": "duckdb_collection_provider.DuckDBCollectionProvider",
       "datasources": {
         "my_datasource": {
           "source": "/path/to/data.parquet",
           "id_col": "cell_id"
         }
       }
     }
   }

Modular Dependency Management
-----------------------------

The project dependencies have been refactored into a "Core" set and several "Optional" extras. This allows for a much smaller installation footprint.

**Core Dependencies:**
* FastAPI & Uvicorn (Web Layer)
* DuckDB & H3 (Data & Grid)
* mapbox-vector-tile & py-ubjson (Encoding & Tiling)

**Optional Extras:**
* ``clickhouse``: Clickhouse DB driver and hashing.
* ``dggrid``: DGGRIDv8 binary and python wrapper.
* ``dggal``: DGGAL grid library.
* ``zarr``: Xarray, Zarr, and Cloud storage support.
* ``scipy``: High-level scientific tools (now optional for default aggregation).

Deployment with Pixi
--------------------

The project now supports `Pixi <https://pixi.sh>`_ for environment management. Pixi is particularly beneficial for this project as it manages the ``dggrid`` C++ binary as a direct dependency, eliminating the need for manual compilation.

**Reproducibility:**
The ``pixi.lock`` file ensures that all developers and production servers use identical versions of all dependencies (Conda and PyPI). **Always commit the ``pixi.lock`` file to version control.**

**First-time Setup:**

.. code-block:: bash

   # Install Pixi (if not already installed)
   curl -fsSL https://pixi.sh/install.sh | bash

   # Clone the repo and install the environment
   git clone <repo_url>
   cd pydggsapi
   pixi install

**Available Environments:**
* ``lean``: Only core dependencies (DuckDB, H3, Tiling). Ideal for the smallest production footprint.
* ``full``: Every supported provider and DGGS system (DGGAL, DGGRID, Clickhouse, Zarr).
* ``database``: Optimized for DuckDB and Clickhouse workflows.
* ``data-science``: Includes Zarr, Xarray, and Scipy.

**Common Commands:**

.. code-block:: bash

   # Start the server using the default (dev) environment
   pixi run start

   # Start the server using the lean environment
   pixi run -e lean start

   # Run all tests
   pixi run test

   # Add a new pypi dependency to the core
   pixi add --pypi my-package

Production Deployment
---------------------

For a robust production deployment on a small Linux server, it is recommended to use **systemd** for process management and **Caddy** as a reverse proxy.

Environment Variables (``.env``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a ``.env`` file in the project root or specify it in the systemd unit. 

.. code-block:: bash

   # Example .env
   # DGGRID_PATH is automatically handled by Pixi if using the 'full' or 'dggrid' feature.
   # For 'lean' environment, you may need to point to an external binary.
   dggs_api_config=/opt/pydggsapi/server/config/dggs_api_config.json
   CORS='["*"]'
   DGGS_PREFIX=/dggs-api/v1-pre
   OPENAPI_URL=/dggs-api/v1-pre/openapi.json
   DOCS_URL=/dggs-api/v1-pre/docs

Systemd Service
^^^^^^^^^^^^^^^

Using Pixi in systemd ensures that the environment is correctly activated before the server starts.

.. code-block:: ini

   [Unit]
   Description=PyDGGS API Service
   After=network.target

   [Service]
   Type=simple
   User=pydggsapi
   Group=pydggsapi
   WorkingDirectory=/opt/pydggsapi
   # Use 'lean' environment for production to minimize footprint
   ExecStart=/usr/local/bin/pixi run --frozen -e lean start
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target

Reverse Proxy (Caddy)
^^^^^^^^^^^^^^^^^^^^^

Caddy simplifies HTTPS management. Ensure both the DGGS API and Tiles API routes are proxied.

.. code-block:: caddy

   portal.example.com {
       handle /dggs-api/v1-pre* {
           reverse_proxy localhost:8000
       }
                         
       handle /tiles-api* {
           reverse_proxy localhost:8000
       }
   }

Orchestration Optimizations
---------------------------
...
The internal data retrieval logic in ``pydggsapi.models.ogc_dggs.data_retrieval`` has been optimized:
* **Vectorized Aggregation:** The expensive ``scipy.stats.mode`` aggregation has been replaced with a high-performance NumPy-based implementation.
* **Defensive Imports:** Optional libraries are now imported locally within specific code paths. This prevents the server from crashing if heavy dependencies like ``xarray`` or ``scipy`` are not installed.
