-- A sealed column holds an `applications::seal` envelope: the key's id, a random nonce and
-- XChaCha20-Poly1305 ciphertext bound to its column, application, row and format. Times are UTC
-- RFC 3339 text.

-- A person's first match supersedes nothing. SQLite changes a CHECK only by rebuilding the table,
-- which `Store::setup` runs with foreign keys off and checks before it commits.
CREATE TABLE matches_rebuilt (
  id                  TEXT PRIMARY KEY,                          -- UUID
  created_at          TEXT NOT NULL,
  client_id           INTEGER REFERENCES api_clients(id),
  user_id             INTEGER REFERENCES users(id),
  supersedes          TEXT UNIQUE REFERENCES matches(id),
  as_of               TEXT NOT NULL,                             -- YYYY-MM-DD
  engine_version      INTEGER NOT NULL,
  format              INTEGER NOT NULL,                          -- matching::MATCH_FORMAT of `input` and `facts`
  analysis_package_id TEXT,
  analysis_revision   TEXT,
  input               TEXT NOT NULL,                             -- JSON MatchInput
  facts               TEXT NOT NULL,                             -- JSON DealFacts as assembled
  CHECK ((client_id IS NULL) <> (user_id IS NULL)),
  CHECK ((analysis_package_id IS NULL) = (analysis_revision IS NULL)),
  CHECK (supersedes IS NULL OR user_id IS NOT NULL)
);
INSERT INTO matches_rebuilt (id, created_at, client_id, user_id, supersedes, as_of, engine_version, format,
                             analysis_package_id, analysis_revision, input, facts)
  SELECT id, created_at, client_id, user_id, supersedes, as_of, engine_version, format,
         analysis_package_id, analysis_revision, input, facts
  FROM matches;
DROP TABLE matches;
ALTER TABLE matches_rebuilt RENAME TO matches;
CREATE TRIGGER matches_no_update BEFORE UPDATE ON matches
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
CREATE TRIGGER matches_no_delete BEFORE DELETE ON matches
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;

-- Identical bytes are one application; another file of the same envelope is another application.
CREATE TABLE applications (
  id                 TEXT PRIMARY KEY,                           -- UUID
  source_sha256      BLOB NOT NULL UNIQUE CHECK (length(source_sha256) = 32),
  envelope_id_sha256 BLOB CHECK (length(envelope_id_sha256) = 32), -- of the certificate's envelope id
  uploaded_at        TEXT NOT NULL,
  uploaded_by        INTEGER NOT NULL REFERENCES users(id),
  source_pdf         BLOB NOT NULL                               -- sealed PDF bytes
);
CREATE INDEX applications_by_envelope ON applications(envelope_id_sha256) WHERE envelope_id_sha256 IS NOT NULL;

-- One parse per parser fingerprint. Only a revision selects one.
CREATE TABLE application_parses (
  id                 TEXT PRIMARY KEY,                           -- UUID
  application_id     TEXT NOT NULL REFERENCES applications(id),
  parser_version     INTEGER NOT NULL,                           -- lender_matching_application::PARSER_VERSION
  parser_fingerprint BLOB NOT NULL CHECK (length(parser_fingerprint) = 32),
  created_at         TEXT NOT NULL,
  format             INTEGER NOT NULL,                           -- applications::PARSE_FORMAT of `payload`
  payload            BLOB NOT NULL,                              -- sealed JSON extract::Reading
  UNIQUE (application_id, parser_fingerprint),
  UNIQUE (application_id, id)
);

-- The highest revision is current. A save on a stale revision is refused.
CREATE TABLE application_revisions (
  application_id    TEXT NOT NULL REFERENCES applications(id),
  revision          INTEGER NOT NULL CHECK (revision >= 1),
  selected_parse_id TEXT NOT NULL,
  saved_at          TEXT NOT NULL,
  author_user_id    INTEGER NOT NULL REFERENCES users(id),
  kind              TEXT NOT NULL CHECK (kind IN ('upload', 'edit', 'adopt_parse', 'confirm_application')),
  cause             TEXT CHECK (cause IN ('reading', 'merchant')),
  format            INTEGER NOT NULL,                            -- applications::STATE_FORMAT of `state`
  state             BLOB NOT NULL,                               -- sealed JSON record::RevisionState
  reason            BLOB,                                        -- sealed text
  PRIMARY KEY (application_id, revision),
  FOREIGN KEY (application_id, selected_parse_id) REFERENCES application_parses(application_id, id),
  CHECK ((kind = 'edit') = (cause IS NOT NULL))
) WITHOUT ROWID;

-- The application revision a match read.
CREATE TABLE match_applications (
  match_id       TEXT PRIMARY KEY REFERENCES matches(id),
  application_id TEXT NOT NULL,
  revision       INTEGER NOT NULL,
  FOREIGN KEY (application_id, revision) REFERENCES application_revisions(application_id, revision)
);
CREATE INDEX match_applications_by_revision ON match_applications(application_id, revision);

CREATE TABLE application_access (
  id             INTEGER PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES applications(id),
  user_id        INTEGER NOT NULL REFERENCES users(id),
  occurred_at    TEXT NOT NULL,
  action         TEXT NOT NULL CHECK (action IN ('reveal'))
);

CREATE TRIGGER applications_no_update BEFORE UPDATE ON applications
BEGIN SELECT RAISE(ABORT, 'applications are immutable'); END;
CREATE TRIGGER applications_no_delete BEFORE DELETE ON applications
BEGIN SELECT RAISE(ABORT, 'applications are immutable'); END;
CREATE TRIGGER application_parses_no_update BEFORE UPDATE ON application_parses
BEGIN SELECT RAISE(ABORT, 'application parses are immutable'); END;
CREATE TRIGGER application_parses_no_delete BEFORE DELETE ON application_parses
BEGIN SELECT RAISE(ABORT, 'application parses are immutable'); END;
CREATE TRIGGER application_revisions_no_update BEFORE UPDATE ON application_revisions
BEGIN SELECT RAISE(ABORT, 'application revisions are immutable'); END;
CREATE TRIGGER application_revisions_no_delete BEFORE DELETE ON application_revisions
BEGIN SELECT RAISE(ABORT, 'application revisions are immutable'); END;
CREATE TRIGGER match_applications_no_update BEFORE UPDATE ON match_applications
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
CREATE TRIGGER match_applications_no_delete BEFORE DELETE ON match_applications
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
CREATE TRIGGER application_access_no_update BEFORE UPDATE ON application_access
BEGIN SELECT RAISE(ABORT, 'the access log is immutable'); END;
CREATE TRIGGER application_access_no_delete BEFORE DELETE ON application_access
BEGIN SELECT RAISE(ABORT, 'the access log is immutable'); END;
