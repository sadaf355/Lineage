from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


class UniqueKeySafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            assert key not in mapping, f"Duplicate key {key!r} found in mapping at {node.start_mark}"
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _get_yaml_files():
    patterns = ["docker-compose*.yml", "deploy/*.yml", ".github/workflows/*.yml"]
    files = []
    for pattern in patterns:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return [p for p in files if p.is_file()]


YAML_FILES = _get_yaml_files()


@pytest.mark.parametrize("file_path", YAML_FILES, ids=[str(p.relative_to(REPO_ROOT)) for p in YAML_FILES])
def test_no_duplicate_keys_in_yaml_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
    list(yaml.load_all(content, Loader=UniqueKeySafeLoader))
