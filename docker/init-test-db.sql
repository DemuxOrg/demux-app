-- Runs once, the first time the Postgres volume is created.
-- Creates the separate database used by the backend test suite.
CREATE DATABASE demux_test;
