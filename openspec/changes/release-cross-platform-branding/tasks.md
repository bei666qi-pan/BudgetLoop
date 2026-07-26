## 1. Version and brand assets

- [x] 1.1 Add a reusable static BudgetLoop interlocking-loop mark to the web application shell and a matching Next.js metadata icon.
- [x] 1.2 Align web, macOS, and Windows package/bundle versions to `0.2.0` without changing launcher prerequisites or credential boundaries.
- [x] 1.3 Add focused web coverage for the persistent branded header and metadata icon contract.

## 2. Cross-platform verification

- [x] 2.1 Run relevant frontend tests and production build; inspect the branded web header at desktop and narrow widths.
- [x] 2.2 Build the macOS archive and verify its bundle version and icon.
- [ ] 2.3 Run the Windows launcher workflow/build gate and verify MSI version and icon.
- [x] 2.4 Run strict OpenSpec validation and the required completed-UI design review; apply and recheck any verified findings.

## 3. Publish and verify

- [x] 3.1 Inspect the reviewed release scope, commit it on the current feature branch, and push it to GitHub.
- [ ] 3.2 Tag the verified commit `v0.2.0`, create the GitHub Release with Windows and macOS assets, checksums, prerequisites, and validation notes.
- [ ] 3.3 Verify the GitHub release assets and public web revision, then record the final delivery evidence.
