# Issue 17 Sub-Issue 1 - Make a Common config.py

Currently the `md_gen` module is working and the next phase would be to update the `md_mgr` with the current gateway API (and other refactors). However, we need to normalize the config.py module to scope the entire project. The configuration must be valid for `md_gen`, `md_mgr`, and later the web app.

The focus of this issue is to move the module `src/md_gen/config.py` to `src/common/config.py`, update the `md_gen` module with the correct imports and json configuration structure.

## Goal

- move the module `src/md_gen/config.py` to `src/common/config.py`
- update the `md_gen` module with the correct imports
- update the `md_gen` configuration to use the current json default structure, where summary and image section where moved inside the `md_gen` property.


