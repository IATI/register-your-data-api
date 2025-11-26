# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Fixed

### Removed

### Security


## [0.1.8] - 2025-11-21

### Added

 - SuiteCRMClientFactory class which generates SuiteCRM clients using a cached
   access token and refreshes the token when needed.

## [0.1.6] - 2025-11-19

### Added

- Initial implemtnation of `GET` `disoverable-reporting-orgs`

## [0.1.5] - 2025-11-19

### Added

- Paging to `GET` `reporting-orgs/{oid}/datasets` endpoint
- Initial implementation of `DELETE` `reporting-orgs/{oid}`

### Removed

- `include_meta` flag from `GET` `reporting-orgs` endpoint

## [0.1.4] - 2025-11-12

### Added

- Update/remove users role for organisation endpoint
- Delete dataset endpoint

## [0.1.3] - 2025-11-05

### Added

- Alembic for database migrations
- Code to handle CONTRIBUTOR_PENDING state

## [0.1.2] - 2025-11-03

### Fixed

- Added iatiRegistryId to required claims

## [0.1.1] - 2025-11-03

### Added

- Create dataset endpoint
- Update dataset endpoint
- Get dataset details endpoint
