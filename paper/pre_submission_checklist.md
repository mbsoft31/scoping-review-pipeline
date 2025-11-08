# Pre‑Submission Checklist for JOSS

This checklist serves as a final reminder to ensure that all required components are ready before submitting the Systematic Review Pipeline to the Journal of Open Source Software.

## Repository preparation

- [ ] Create a release version (v1.5.0) tagged in Git and archived on Zenodo.
- [ ] Obtain a DOI from Zenodo and update the badge in the project README.
- [ ] Ensure that all tests pass on the continuous integration service.
- [ ] Update the documentation to reflect the latest changes.
- [ ] Add a `CITATION.cff` file to the repository.
- [ ] Review all open issues and pull requests; either resolve or postpone them.

## Paper preparation

- [ ] Proofread `paper.md` for typos and grammar.
- [ ] Verify that all citations include DOIs where available.
- [ ] Check reference formatting in `paper.bib`.
- [ ] Ensure that figures and tables render correctly.
- [ ] Add author ORCID identifiers and complete affiliations.
- [ ] Write the acknowledgments and declare competing interests.

## Code quality

- [ ] Run the full test suite locally and in CI.
- [ ] Check that code coverage remains above 70%.
- [ ] Run the linter and address any remaining style issues.
- [ ] Update dependencies to the latest stable versions where possible.
- [ ] Remove any lingering debug code or print statements.
- [ ] Ensure all public functions have docstrings and appropriate type hints.
- [ ] Review and update inline comments for clarity.

## Documentation

- [ ] Test the installation instructions on a clean system.
- [ ] Confirm that example scripts run without errors.
- [ ] Verify that API documentation is complete and accurate.
- [ ] Execute tutorial notebooks and ensure they run end‑to‑end.
- [ ] Update the troubleshooting guide and FAQ section.

## Legal and ethics

- [ ] Verify that all dependencies have compatible licenses.
- [ ] Ensure that permissions for included datasets are in place and documented.
- [ ] Confirm that IRB approval covers all human subjects research.
- [ ] Review privacy implications of example data and anonymize as needed.
- [ ] Check that no proprietary code or datasets are included without permission.

## Submission materials

- [ ] Include `paper.md` and `paper.bib` in the submission package.
- [ ] Generate a `codemeta.json` file for metadata.
- [ ] Place all figures used in the paper in the appropriate directory.
- [ ] Confirm that `README.md` explains the software’s purpose and usage.
- [ ] Ensure that `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `LICENSE` files are present and up‑to‑date.

## Final steps

- [ ] Submit via the JOSS web interface.
- [ ] Respond promptly to reviewer comments.
- [ ] Make requested changes in a timely manner.
- [ ] Update the paper and software based on feedback.
- [ ] Celebrate acceptance! 🎉