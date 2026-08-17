"""initial schema

Revision ID: 0002_initial_schema
Revises: 0001_enable_postgis
Create Date: 2026-08-17

SQL figé, généré depuis Base.metadata (17 tables). Ne pas régénérer : c'est le
snapshot historique du schéma. Les évolutions passent par de nouvelles migrations.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_initial_schema"
down_revision: str | None = "0001_enable_postgis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_STATEMENTS: list[str] = [
    r'''CREATE TABLE data_quality_issue (
	id BIGSERIAL NOT NULL, 
	entity_type VARCHAR(60) NOT NULL, 
	entity_id BIGINT, 
	rule VARCHAR(80) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	detected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	details JSONB, 
	PRIMARY KEY (id)
)''',
    r'''CREATE INDEX ix_dq_entity ON data_quality_issue (entity_type, entity_id)''',
    r'''CREATE TABLE data_source (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	provider VARCHAR(200), 
	url TEXT, 
	access_method VARCHAR(120), 
	license VARCHAR(120), 
	terms_url TEXT, 
	refresh_frequency VARCHAR(120), 
	free BOOLEAN NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	last_checked_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)''',
    r'''CREATE TABLE region (
	insee_code VARCHAR(3) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	PRIMARY KEY (insee_code)
)''',
    r'''CREATE TABLE department (
	insee_code VARCHAR(3) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	region_code VARCHAR(3), 
	PRIMARY KEY (insee_code), 
	FOREIGN KEY(region_code) REFERENCES region (insee_code)
)''',
    r'''CREATE INDEX ix_department_region_code ON department (region_code)''',
    r'''CREATE TABLE ingestion_batch (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(32) NOT NULL, 
	source_version VARCHAR(120), 
	file_hash VARCHAR(64), 
	rows_read INTEGER NOT NULL, 
	rows_inserted INTEGER NOT NULL, 
	rows_updated INTEGER NOT NULL, 
	rows_rejected INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES data_source (id)
)''',
    r'''CREATE INDEX ix_ingestion_batch_source_id ON ingestion_batch (source_id)''',
    r'''CREATE TABLE job_run (
	id BIGSERIAL NOT NULL, 
	job_type VARCHAR(80) NOT NULL, 
	source_id BIGINT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(32) NOT NULL, 
	items_read INTEGER NOT NULL, 
	items_inserted INTEGER NOT NULL, 
	items_updated INTEGER NOT NULL, 
	items_rejected INTEGER NOT NULL, 
	error_message TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES data_source (id)
)''',
    r'''CREATE INDEX ix_job_run_job_type ON job_run (job_type)''',
    r'''CREATE INDEX ix_job_run_source_id ON job_run (source_id)''',
    r'''CREATE TABLE commune (
	insee_code VARCHAR(5) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	department_code VARCHAR(3), 
	postal_codes VARCHAR(200), 
	PRIMARY KEY (insee_code), 
	FOREIGN KEY(department_code) REFERENCES department (insee_code)
)''',
    r'''CREATE INDEX ix_commune_department_code ON commune (department_code)''',
    r'''CREATE TABLE dpe (
	id BIGSERIAL NOT NULL, 
	identifiant_ban VARCHAR(60), 
	insee_code VARCHAR(5), 
	postal_code VARCHAR(5), 
	address TEXT, 
	surface_habitable_m2 NUMERIC(10, 2), 
	etiquette_dpe VARCHAR(1), 
	etiquette_ges VARCHAR(1), 
	date_etablissement DATE, 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	location geography(POINT,4326), 
	ingestion_batch_id BIGINT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ingestion_batch_id) REFERENCES ingestion_batch (id)
)''',
    r'''CREATE INDEX ix_dpe_location ON dpe USING gist (location)''',
    r'''CREATE INDEX ix_dpe_insee_code ON dpe (insee_code)''',
    r'''CREATE INDEX ix_dpe_identifiant_ban ON dpe (identifiant_ban)''',
    r'''CREATE TABLE iris (
	code VARCHAR(9) NOT NULL, 
	commune_code VARCHAR(5), 
	name VARCHAR(200), 
	PRIMARY KEY (code), 
	FOREIGN KEY(commune_code) REFERENCES commune (insee_code)
)''',
    r'''CREATE INDEX ix_iris_commune_code ON iris (commune_code)''',
    r'''CREATE TABLE property (
	id BIGSERIAL NOT NULL, 
	property_type VARCHAR(20) NOT NULL, 
	normalized_address TEXT, 
	postal_code VARCHAR(5), 
	city VARCHAR(200), 
	insee_code VARCHAR(5), 
	location geography(POINT,4326), 
	surface_m2 NUMERIC(10, 2), 
	land_surface_m2 NUMERIC(12, 2), 
	rooms SMALLINT, 
	bedrooms SMALLINT, 
	construction_year SMALLINT, 
	energy_rating VARCHAR(1), 
	ghg_rating VARCHAR(1), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insee_code) REFERENCES commune (insee_code)
)''',
    r'''CREATE INDEX ix_property_location ON property USING gist (location)''',
    r'''CREATE INDEX ix_property_insee_code ON property (insee_code)''',
    r'''CREATE TABLE transaction_dvf (
	id BIGSERIAL NOT NULL, 
	id_mutation VARCHAR(40) NOT NULL, 
	mutation_date DATE, 
	mutation_type VARCHAR(80), 
	sale_price NUMERIC(12, 2), 
	property_type VARCHAR(20) NOT NULL, 
	surface_m2 NUMERIC(10, 2), 
	land_surface_m2 NUMERIC(12, 2), 
	rooms SMALLINT, 
	raw_address TEXT, 
	normalized_address TEXT, 
	postal_code VARCHAR(5), 
	city VARCHAR(200), 
	insee_code VARCHAR(5), 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	location geography(POINT,4326), 
	parcel_id VARCHAR(20), 
	price_per_m2 NUMERIC(12, 2), 
	source_year SMALLINT, 
	source_row_reference VARCHAR(120), 
	quality_flag VARCHAR(40), 
	ingestion_batch_id BIGINT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(insee_code) REFERENCES commune (insee_code), 
	FOREIGN KEY(ingestion_batch_id) REFERENCES ingestion_batch (id)
)''',
    r'''CREATE INDEX ix_transaction_dvf_id_mutation ON transaction_dvf (id_mutation)''',
    r'''CREATE INDEX ix_transaction_dvf_insee_code ON transaction_dvf (insee_code)''',
    r'''CREATE INDEX ix_transaction_dvf_location ON transaction_dvf USING gist (location)''',
    r'''CREATE INDEX ix_transaction_dvf_insee_date ON transaction_dvf (insee_code, mutation_date)''',
    r'''CREATE INDEX ix_transaction_dvf_parcel_id ON transaction_dvf (parcel_id)''',
    r'''CREATE TABLE listing (
	id BIGSERIAL NOT NULL, 
	source_id BIGINT NOT NULL, 
	external_listing_id VARCHAR(120) NOT NULL, 
	canonical_property_id BIGINT, 
	canonical_url TEXT, 
	status VARCHAR(20) NOT NULL, 
	source_publication_date DATE, 
	first_seen_at TIMESTAMP WITH TIME ZONE, 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	last_checked_at TIMESTAMP WITH TIME ZONE, 
	history_origin VARCHAR(32) NOT NULL, 
	parser_version VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_listing_source_external UNIQUE (source_id, external_listing_id), 
	FOREIGN KEY(source_id) REFERENCES data_source (id), 
	FOREIGN KEY(canonical_property_id) REFERENCES property (id)
)''',
    r'''CREATE INDEX ix_listing_canonical_property_id ON listing (canonical_property_id)''',
    r'''CREATE INDEX ix_listing_first_seen_at ON listing (first_seen_at)''',
    r'''CREATE INDEX ix_listing_status ON listing (status)''',
    r'''CREATE TABLE property_match_candidate (
	id BIGSERIAL NOT NULL, 
	property_a_id BIGINT NOT NULL, 
	property_b_id BIGINT NOT NULL, 
	match_score NUMERIC(5, 4) NOT NULL, 
	matching_version VARCHAR(40) NOT NULL, 
	matching_features JSONB, 
	review_status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_a_id) REFERENCES property (id), 
	FOREIGN KEY(property_b_id) REFERENCES property (id)
)''',
    r'''CREATE INDEX ix_property_match_candidate_property_b_id ON property_match_candidate (property_b_id)''',
    r'''CREATE INDEX ix_property_match_candidate_property_a_id ON property_match_candidate (property_a_id)''',
    r'''CREATE TABLE dvf_match_candidate (
	id BIGSERIAL NOT NULL, 
	listing_id BIGINT NOT NULL, 
	transaction_dvf_id BIGINT NOT NULL, 
	confidence NUMERIC(5, 4) NOT NULL, 
	matching_version VARCHAR(40) NOT NULL, 
	matching_features JSONB, 
	review_status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(listing_id) REFERENCES listing (id), 
	FOREIGN KEY(transaction_dvf_id) REFERENCES transaction_dvf (id)
)''',
    r'''CREATE INDEX ix_dvf_match_candidate_transaction_dvf_id ON dvf_match_candidate (transaction_dvf_id)''',
    r'''CREATE INDEX ix_dvf_match_candidate_listing_id ON dvf_match_candidate (listing_id)''',
    r'''CREATE TABLE listing_check (
	id BIGSERIAL NOT NULL, 
	listing_id BIGINT NOT NULL, 
	checked_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	found BOOLEAN NOT NULL, 
	http_status INTEGER, 
	duration_ms INTEGER, 
	parser_success BOOLEAN, 
	error_code VARCHAR(40), 
	PRIMARY KEY (id), 
	FOREIGN KEY(listing_id) REFERENCES listing (id)
)''',
    r'''CREATE INDEX ix_listing_check_listing_id ON listing_check (listing_id)''',
    r'''CREATE TABLE listing_snapshot (
	id BIGSERIAL NOT NULL, 
	listing_id BIGINT NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	price_eur NUMERIC(12, 2), 
	price_per_m2 NUMERIC(12, 2), 
	title TEXT, 
	surface_m2 NUMERIC(10, 2), 
	land_surface_m2 NUMERIC(12, 2), 
	rooms SMALLINT, 
	bedrooms SMALLINT, 
	energy_rating VARCHAR(1), 
	ghg_rating VARCHAR(1), 
	seller_type VARCHAR(40), 
	agency_name VARCHAR(200), 
	city VARCHAR(200), 
	postal_code VARCHAR(5), 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	location geography(POINT,4326), 
	photo_count INTEGER, 
	description_hash VARCHAR(64), 
	photo_fingerprint TEXT, 
	payload_hash VARCHAR(64) NOT NULL, 
	pipeline_version VARCHAR(40), 
	parser_version VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(listing_id) REFERENCES listing (id)
)''',
    r'''CREATE INDEX ix_listing_snapshot_listing_observed ON listing_snapshot (listing_id, observed_at)''',
    r'''CREATE INDEX ix_listing_snapshot_location ON listing_snapshot USING gist (location)''',
    r'''CREATE TABLE listing_event (
	id BIGSERIAL NOT NULL, 
	listing_id BIGINT NOT NULL, 
	event_type VARCHAR(32) NOT NULL, 
	event_date TIMESTAMP WITH TIME ZONE NOT NULL, 
	old_value TEXT, 
	new_value TEXT, 
	event_metadata JSONB, 
	snapshot_id BIGINT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(listing_id) REFERENCES listing (id), 
	FOREIGN KEY(snapshot_id) REFERENCES listing_snapshot (id)
)''',
    r'''CREATE INDEX ix_listing_event_listing_date ON listing_event (listing_id, event_date)''',
]

DROP_STATEMENTS: list[str] = [
    r'''DROP TABLE IF EXISTS listing_event CASCADE''',
    r'''DROP TABLE IF EXISTS listing_snapshot CASCADE''',
    r'''DROP TABLE IF EXISTS listing_check CASCADE''',
    r'''DROP TABLE IF EXISTS dvf_match_candidate CASCADE''',
    r'''DROP TABLE IF EXISTS property_match_candidate CASCADE''',
    r'''DROP TABLE IF EXISTS listing CASCADE''',
    r'''DROP TABLE IF EXISTS transaction_dvf CASCADE''',
    r'''DROP TABLE IF EXISTS property CASCADE''',
    r'''DROP TABLE IF EXISTS iris CASCADE''',
    r'''DROP TABLE IF EXISTS dpe CASCADE''',
    r'''DROP TABLE IF EXISTS commune CASCADE''',
    r'''DROP TABLE IF EXISTS job_run CASCADE''',
    r'''DROP TABLE IF EXISTS ingestion_batch CASCADE''',
    r'''DROP TABLE IF EXISTS department CASCADE''',
    r'''DROP TABLE IF EXISTS region CASCADE''',
    r'''DROP TABLE IF EXISTS data_source CASCADE''',
    r'''DROP TABLE IF EXISTS data_quality_issue CASCADE''',
]


def upgrade() -> None:
    for stmt in CREATE_STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DROP_STATEMENTS:
        op.execute(stmt)
