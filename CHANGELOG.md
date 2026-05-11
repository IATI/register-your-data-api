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

## [0.3.6] - 2026-05-06

### Changed

- Upgraded `libsuitecrm` to 0.5.2 to bring in fix for SuiteCRM's over-zealous HTML escaping.

### Fixed

- Updated the EDITOR role to have permission to set visibility on datasets.

## [0.3.5] - 2026-04-28

### Added

- Tools list endpoint and associated test.
- User roles endpoint and associated test; and a placeholder for the related permissions endpoint.
- Provider admin management endpoint placeholders and tests.

### Changed

- FGA Provider now stores tool client IDs and can handle multiple provider_admin roles per user per reporting
  orgs to accommodate multiple tools being able to access the same reporting org via provider_admin.
- FGA Validator now ingests a list of tools that the user is an admin user for and the client id of the calling
  application.
- FGA Validator restricts provider_admin access to only the client id associated with that tool.
- Tests for the FGA provider DB and validator.
- Changes to the tests for dataset and reporting org routes so that calls via provider_admin can use the correct client id.


## [0.3.4] - 2026-04-20

### Fixed

 - Dataset creation endpoint now returns 201 rather than 200.

### Changed

 - Permissions for provider admin user role.

### Added

 - Integration tests for creating and deleting datasets, and updating organisations.


## [0.3.3] - 2026-04-15

### Added

 - New provider admin database models for the FGA database provider.

### Changed

 - Refactored provider admin code in the FGA validator and database provider.

### Fixed

 - Small fix to correct a failing test.


## [0.3.1] - 2026-03-17

### Added

 - Added the ability to search the discoverable reporting orgs.

## [0.3.0]

### Added

 - Added the /users/{id}/reporting-orgs endpoint which allows lookup of a user's
   orgs by user id.

### Fixed

 - Updated short name validation so that it rejects values with uppercase
   characters.
 - Improves error handling and logging for when clients connect with a
   misconfigured client ID.

## [0.2.9]

### Added

 - Emails notifications to Secretariat admins when a user creates a new
   organisation and to organisation admins when a user requests to join their
   organisation.

## [0.2.8]

### Added

 - Improved and adding more audit logging.

### Fixed

 - Fixed the validation on dataset short_name which wasn't checking whether the
   record in the CRM was deleted.

## [0.2.7]

### Fixed

 - Fixed the dataset PATCH endpoint to include validation of the dataset
   short_name field.

## [0.2.6]

### Added

 - Added paging to GET /reporting-orgs, as per the specification.

### Fixed

 - Fixed the 'last' paging link when there are no results to point to page 1.

## [0.2.5]

### Fixed

 - Made the utility check_record_exists function more robust by limiting fields
   returned.

### Removed

### Security

## [0.2.4]

### Added

 - Dataset actions returned on /dataset/{id} and /reporting-orgs/{id}/dataset
   endpoints.

## [0.2.3] - 2025-12-08

### Added

 - Validation of dataset, reporting_org short_name to alphanumeric, '-', '_' chars
 - On record creation, check dataset, reporting_org short_name for uniqueness

### Fixed

 - Ensured that newly created reporting orgs are made discoverable on the Registry.

## [0.2.2] - 2025-12-04

### Changed

 - Removed auto-redirect on trailing slashes

### Fixed

 - Unified all endpoints to not have any trailing slashes

## [0.2.1] - 2025-11-30

### Added

 - Send custom audit headers to Registry on write requests.

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
