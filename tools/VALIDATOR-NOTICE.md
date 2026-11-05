# Validator contents

`import-validator.jar` is built from the SmartVoice ZIP/import/resource validation classes and JSON-java (20240303). It contains no voice models, native synthesis libraries, signing keys, GitHub credentials or Android stubs. Sources and rebuild script are in the matching SmartVoice 5.2.53 source distribution (`offline_build_tools/CatalogImportValidator.java`, `build_catalog_validator.py`, `umedjon_dex2_src`). Its scope is structural import validation, not audio/quality certification.

JSON-java, Copyright (c) 2002 JSON.org, is used under its Public Domain license. Upstream: https://github.com/stleary/JSON-java/tree/20240303 . See https://github.com/stleary/JSON-java/blob/20240303/LICENSE for the upstream license notice.
