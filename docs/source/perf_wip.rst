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

The server loads environment variables from a ``.env`` file by default. You can specify a custom path using the ``PYDGGSAPI_ENV`` variable.

**Example and Working Settings:**

.. code-block:: bash

   # Path to the TinyDB configuration file
   dggs_api_config=server/config/dggs_api_config_example.json

   # DGGRID binary path (automatically handled by Pixi in 'full' or 'dggrid' envs)
   # For 'lean' production, point to your local binary:
   # DGGRID_PATH=/usr/local/bin/dggrid

   # API Metadata
   API_TITLE="University of Tartu, OGC DGGS API v1-pre"
   API_DESCRIPTION="OGC DGGS API"
   API_CONTACT="info@geolynx.ee"

   # OGC API & Router Settings
   CORS='["*"]'
   DGGS_PREFIX=/dggs-api/v1-pre
   OPENAPI_URL=/dggs-api/v1-pre/openapi.json
   DOCS_URL=/dggs-api/v1-pre/docs

   # Server performance
   PYDGDSAPI_WORKERS=1
   LOGLEVEL=10  # DEBUG

**Robust Metadata Parsing:**
The ``API_CONTACT`` field now supports both plain email strings and JSON objects (e.g., ``{"name": "...", "email": "..."}``). If a plain string is provided, it is automatically converted to a standard contact object.

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

The internal orchestration logic has been hardened for development and production:

* **Vectorized Aggregation:** The expensive ``scipy.stats.mode`` aggregation has been replaced with a high-performance NumPy-based implementation (``_fast_mode``).
* **Defensive Imports:** Optional libraries (``scipy``, ``zarr``, ``xarray``) are now imported locally. This allows the server to run core providers even if heavy extras are missing.
* **Resilient Metadata:** Version lookup and contact parsing are now defensive, allowing the server to start gracefully even if package metadata is missing or environment variables are simple strings.
* **Deterministic Startup:** The initialization sequence ensures that environment variables are loaded via ``load_dotenv`` before any sub-routers (which might depend on them) are imported.
