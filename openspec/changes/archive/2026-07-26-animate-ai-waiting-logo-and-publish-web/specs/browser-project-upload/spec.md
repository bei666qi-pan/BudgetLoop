## ADDED Requirements

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

### Requirement: Browser upload and native access remain distinct
The frontend SHALL label browser selection as uploading an isolated project copy and SHALL reserve direct-project/full-access wording for the macOS native folder bridge.

#### Scenario: Native bridge is unavailable
- **WHEN** the operator activates the project-folder action in a normal browser
- **THEN** the browser opens a folder upload picker, explains that the Agent receives an isolated copy, and does not request or display a host absolute path

#### Scenario: Native bridge is available
- **WHEN** the same action is used inside the BudgetLoop macOS App
- **THEN** the existing native folder picker and explicit full-access acknowledgement remain available without first uploading the folder

### Requirement: Recoverable upload feedback
The frontend SHALL expose upload progress or busy state, a success summary, and an actionable error while preserving the user's goal and current draft.

#### Scenario: Folder upload fails
- **WHEN** the upload API rejects or cannot store the folder snapshot
- **THEN** the interface keeps the goal and draft intact, identifies the upload failure in plain language and allows the operator to choose the folder again
