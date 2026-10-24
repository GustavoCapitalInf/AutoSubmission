-- Migration 3: blind audits. An `audit` revision holds what a person typed from page 1 before any
-- parser value was visible, and `application_access` also logs each opening of an audit page.
-- SQLite changes a CHECK only by rebuilding the table, which `Store::setup` runs with foreign keys
-- off and checks before it commits.
CREATE TABLE application_revisions_rebuilt (
  application_id    TEXT NOT NULL REFERENCES applications(id),
  revision          INTEGER NOT NULL CHECK (revision >= 1),
  selected_parse_id TEXT NOT NULL,
  saved_at          TEXT NOT NULL,
  author_user_id    INTEGER NOT NULL REFERENCES users(id),
  kind              TEXT NOT NULL CHECK (kind IN ('upload', 'edit', 'adopt_parse', 'confirm_application', 'audit')),
  cause             TEXT CHECK (cause IN ('reading', 'merchant')),
  format            INTEGER NOT NULL,                            -- applications::STATE_FORMAT of `state`
  state             BLOB NOT NULL,                               -- sealed JSON record::RevisionState
  reason            BLOB,                                        -- sealed text
  PRIMARY KEY (application_id, revision),
  FOREIGN KEY (application_id, selected_parse_id) REFERENCES application_parses(application_id, id),
  CHECK ((kind = 'edit') = (cause IS NOT NULL))
) WITHOUT ROWID;
INSERT INTO application_revisions_rebuilt (application_id, revision, selected_parse_id, saved_at, author_user_id,
                                           kind, cause, format, state, reason)
  SELECT application_id, revision, selected_parse_id, saved_at, author_user_id, kind, cause, format, state, reason
  FROM application_revisions;
DROP TABLE application_revisions;
ALTER TABLE application_revisions_rebuilt RENAME TO application_revisions;
CREATE TRIGGER application_revisions_no_update BEFORE UPDATE ON application_revisions
BEGIN SELECT RAISE(ABORT, 'application revisions are immutable'); END;
CREATE TRIGGER application_revisions_no_delete BEFORE DELETE ON application_revisions
BEGIN SELECT RAISE(ABORT, 'application revisions are immutable'); END;

CREATE TABLE application_access_rebuilt (
  id             INTEGER PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES applications(id),
  user_id        INTEGER NOT NULL REFERENCES users(id),
  occurred_at    TEXT NOT NULL,
  action         TEXT NOT NULL CHECK (action IN ('reveal', 'audit'))
);
INSERT INTO application_access_rebuilt (id, application_id, user_id, occurred_at, action)
  SELECT id, application_id, user_id, occurred_at, action FROM application_access;
DROP TABLE application_access;
ALTER TABLE application_access_rebuilt RENAME TO application_access;
CREATE TRIGGER application_access_no_update BEFORE UPDATE ON application_access
BEGIN SELECT RAISE(ABORT, 'the access log is immutable'); END;
CREATE TRIGGER application_access_no_delete BEFORE DELETE ON application_access
BEGIN SELECT RAISE(ABORT, 'the access log is immutable'); END;
