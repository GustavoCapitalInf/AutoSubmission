use std::path::{Component, Path, PathBuf, Prefix};

pub struct DataDir(PathBuf);

impl DataDir {
    /// `given` comes from `--data-dir` or `LENDER_MATCHING_DATA_DIR`; without it, the OS data
    /// directory (`%APPDATA%\CapitalInfusion\LenderMatching` on Windows, `$XDG_DATA_HOME/lender-matching`
    /// on Linux). Creates the directory. Refuses one inside a git work tree, so the database cannot
    /// be committed, and one on a network share, where SQLite locking is unreliable.
    pub fn resolve(given: Option<PathBuf>) -> Result<DataDir, String> {
        let path = match given {
            Some(path) => path,
            None => default_dir().ok_or("no OS data directory is known; pass --data-dir")?,
        };
        if is_network_share(&path) {
            return Err(format!("{} is on a network share; use a local disk", path.display()));
        }
        std::fs::create_dir_all(&path).map_err(|error| format!("cannot create {}: {error}", path.display()))?;
        // On Windows the canonical form is a `\\?\` path, and a mapped network drive resolves to
        // `\\?\UNC\…`; it serves the checks, and the database opens through the plain absolute path.
        let canonical =
            std::fs::canonicalize(&path).map_err(|error| format!("cannot open {}: {error}", path.display()))?;
        if is_network_share(&canonical) {
            return Err(format!("{} is on a network share; use a local disk", path.display()));
        }
        if let Some(tree) = canonical.ancestors().find(|dir| dir.join(".git").exists()) {
            return Err(format!(
                "{} is inside the git work tree {}; keep the database outside every checkout",
                path.display(),
                tree.display()
            ));
        }
        let absolute =
            std::path::absolute(&path).map_err(|error| format!("cannot open {}: {error}", path.display()))?;
        Ok(DataDir(absolute))
    }

    pub fn path(&self) -> &Path {
        &self.0
    }

    pub fn database(&self) -> PathBuf {
        self.0.join("lender-matching.sqlite3")
    }
}

fn default_dir() -> Option<PathBuf> {
    let base = dirs::data_dir()?;
    Some(if cfg!(windows) { base.join("CapitalInfusion").join("LenderMatching") } else { base.join("lender-matching") })
}

fn is_network_share(path: &Path) -> bool {
    match path.components().next() {
        Some(Component::Prefix(prefix)) => matches!(prefix.kind(), Prefix::UNC(..) | Prefix::VerbatimUNC(..)),
        _ => path.to_string_lossy().starts_with(r"\\") && !path.to_string_lossy().starts_with(r"\\?\"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_directory_inside_a_git_work_tree_is_refused() {
        let inside = Path::new(env!("CARGO_MANIFEST_DIR")).join("target").join("data-dir-test");
        let error = DataDir::resolve(Some(inside.clone())).err().unwrap();
        assert!(error.contains("git work tree"), "{error}");
        let _ = std::fs::remove_dir_all(inside);
    }

    #[test]
    fn a_directory_outside_any_work_tree_is_created() {
        let outside = std::env::temp_dir().join(format!("lender-matching-data-{}", uuid::Uuid::new_v4()));
        let dir = DataDir::resolve(Some(outside.clone())).unwrap();
        assert!(dir.path().is_dir());
        assert_eq!(dir.database().file_name().unwrap(), "lender-matching.sqlite3");
        std::fs::remove_dir_all(outside).unwrap();
    }

    #[test]
    fn network_shares_are_recognized() {
        assert!(is_network_share(Path::new(r"\\fileserver\share\lender-matching")));
        assert!(!is_network_share(Path::new("relative/lender-matching")));
    }
}
