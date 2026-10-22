# Output pins

These files pin the bytes each statement and package route serves for fabricated jobs. The test module
`tests/test_output_characterization.py` checks them. There is one folder per case.

`fingerprints.txt` has one line per served file: its path, the SHA-256 of the fresh read, and the reloaded read's
SHA-256, or `same` when a job store reopened on the same folder serves the fresh bytes. A route that does not answer
200 shows `http-<status>:` before the digest of its body. An XLSX has one line per zip part plus `parts.txt`, the
part list with each part's compression, and the creation time in `docProps/core.xml` is masked. `package.csv` is the
package CSV download of the fresh read, byte for byte, for a reviewer to read.

To see what changed, run the module with `OUTPUT_PINS_DUMP=<folder outside the repository>` at the parent commit and
at the head, into two folders, and diff them. The dump has every served body, one folder per case, with the API JSON
indented and each sheet row on its own line.

To regenerate after a deliberate output change, run this from the package folder:

    UPDATE_OUTPUT_PINS=1 python -m pytest tests/test_output_characterization.py
