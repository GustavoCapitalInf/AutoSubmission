-- Migration 1. Times are UTC RFC 3339 text.

CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_phc  TEXT NOT NULL,                                   -- argon2id PHC string
  role          TEXT NOT NULL CHECK (role IN ('viewer', 'reviewer', 'editor')),
  created_at    TEXT NOT NULL,
  disabled_at   TEXT
);

CREATE TABLE sessions (
  token_sha256  BLOB PRIMARY KEY CHECK (length(token_sha256) = 32),
  user_id       INTEGER NOT NULL REFERENCES users(id),
  csrf_token    TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  expires_at    TEXT NOT NULL
);

CREATE TABLE api_clients (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  token_sha256  BLOB NOT NULL UNIQUE CHECK (length(token_sha256) = 32),
  scopes        TEXT NOT NULL,                                   -- space-separated, sorted: match read
  created_at    TEXT NOT NULL,
  revoked_at    TEXT
);
CREATE UNIQUE INDEX api_clients_live_name ON api_clients(name) WHERE revoked_at IS NULL;

CREATE TABLE industries (
  slug          TEXT PRIMARY KEY,
  label         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  retired_at    TEXT
);
CREATE TRIGGER industries_kept BEFORE DELETE ON industries
BEGIN SELECT RAISE(ABORT, 'stored rules name industries by slug; retire it instead'); END;

CREATE TABLE import_runs (
  id            INTEGER PRIMARY KEY,
  run_at        TEXT NOT NULL,
  source_sha256 BLOB NOT NULL CHECK (length(source_sha256) = 32),
  readings      TEXT NOT NULL,                                   -- JSON ImportReadings
  report        TEXT NOT NULL                                    -- JSON ImportReport
);

CREATE TABLE lenders (
  id            TEXT PRIMARY KEY,                                -- lnd_ and 10 base32 characters
  import_key    TEXT UNIQUE,                                     -- record:<id> or name:<normalized>; null when an admin created it
  created_at    TEXT NOT NULL
);

-- The only store of a lender's criteria and details. The highest revision is current.
CREATE TABLE lender_revisions (
  lender_id            TEXT NOT NULL REFERENCES lenders(id),
  revision             INTEGER NOT NULL CHECK (revision >= 1),
  saved_at             TEXT NOT NULL,
  author_user_id       INTEGER REFERENCES users(id),
  author_import_run_id INTEGER REFERENCES import_runs(id),
  reason               TEXT,
  format               INTEGER NOT NULL,                         -- criteria::RECORD_FORMAT of `record`
  record               TEXT NOT NULL,                            -- canonical JSON LenderRecord
  PRIMARY KEY (lender_id, revision),
  CHECK ((author_user_id IS NULL) <> (author_import_run_id IS NULL))
) WITHOUT ROWID;
CREATE TRIGGER lender_revisions_no_update BEFORE UPDATE ON lender_revisions
BEGIN SELECT RAISE(ABORT, 'lender revisions are immutable'); END;
CREATE TRIGGER lender_revisions_no_delete BEFORE DELETE ON lender_revisions
BEGIN SELECT RAISE(ABORT, 'lender revisions are immutable'); END;

CREATE VIEW lender_heads AS
  SELECT r.* FROM lender_revisions r
  WHERE r.revision = (SELECT MAX(x.revision) FROM lender_revisions x WHERE x.lender_id = r.lender_id);

-- A match made by a machine client, or by a signed-in person who superseded an earlier match.
CREATE TABLE matches (
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
  CHECK ((supersedes IS NULL) = (user_id IS NULL))
);
CREATE TRIGGER matches_no_update BEFORE UPDATE ON matches
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
CREATE TRIGGER matches_no_delete BEFORE DELETE ON matches
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;

-- Which revision of every lender a match read, and what it concluded.
CREATE TABLE match_verdicts (
  match_id    TEXT NOT NULL REFERENCES matches(id),
  lender_id   TEXT NOT NULL,
  revision    INTEGER NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('match', 'review', 'no_match', 'inactive', 'not_offered')),
  evaluation  TEXT,                                              -- JSON Evaluation; null when not evaluated
  PRIMARY KEY (match_id, lender_id),
  FOREIGN KEY (lender_id, revision) REFERENCES lender_revisions(lender_id, revision),
  CHECK ((status IN ('inactive', 'not_offered')) = (evaluation IS NULL))
) WITHOUT ROWID;
CREATE TRIGGER match_verdicts_no_update BEFORE UPDATE ON match_verdicts
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
CREATE TRIGGER match_verdicts_no_delete BEFORE DELETE ON match_verdicts
BEGIN SELECT RAISE(ABORT, 'matches are immutable'); END;
