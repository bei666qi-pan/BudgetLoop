# browser-project-upload Specification

## Purpose

Define secure, bounded browser folder snapshot upload and the trustworthy distinction between isolated uploads and native direct-folder access.

## Requirements

### Requirement: Explicit browser folder snapshot upload
The authenticated web API SHALL accept a browser-selected folder only as a bounded multipart snapshot of regular files, SHALL validate every relative path and configured size/count limit before publishing the snapshot, and SHALL return an opaque upload identifier and non-sensitive summary without returning a server filesystem path.

#### Scenario: Valid folder is uploaded
- **WHEN** a browser submits regular files with unique normalized relative paths within every configured limit
- **THEN** the API atomically stores the snapshot below the private upload root and returns an opaque identifier, file count and total byte count

#### Scenario: Upload path attempts to escape
- **WHEN** any submitted relative path is absolute, empty, duplicated, contains parent traversal or resolves outside the staging directory
- **THEN** the API rejects the complete upload, removes partial files and publishes no usable identifier

#### Scenario: Upload exceeds a bound
- **WHEN** the file count, a single file size or aggregate bytes exceed the configured limit
- **THEN** the API stops processing, returns a readable bounded-upload error and removes the partial upload

### Requirement: Browser upload and manual full access remain distinct
The frontend SHALL label browser selection as uploading an isolated project copy and allow manual absolute path entry for full-access mode.

#### Scenario: Browser invokes upload for isolated mode
- **WHEN** the operator activates the project-folder action in a normal browser
- **THEN** the browser opens a folder upload picker, explains that the Agent receives an isolated copy, and does not request or display a host absolute path

#### Scenario: Full access via manual path entry
- **WHEN** the operator selects 完全访问模式 and types an absolute path
- **THEN** the form accepts the manual path, validates it on submission alongside acknowledgement, and persists it for direct mount provisioning

### Requirement: Recoverable upload feedback
The frontend SHALL expose upload progress or busy state, a success summary, and an actionable error while preserving the user's goal and current draft.

#### Scenario: Folder upload fails
- **WHEN** the upload API rejects or cannot store the folder snapshot
- **THEN** the interface keeps the goal and draft intact, identifies the upload failure in plain language and allows the operator to choose the folder again
