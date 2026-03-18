from __future__ import annotations

import tempfile
import unittest

from canirunai.collectors.seed_catalog import cpu_seed_specs
from canirunai.store.json_store import JsonStore


class JsonStoreTest(unittest.TestCase):
    def test_merge_replaces_existing_item_by_lookup_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JsonStore(data_dir=tmp_dir, raw_cache_dir=f"{tmp_dir}/raw_cache")
            original = cpu_seed_specs()[0]
            updated = original.model_copy(update={"canonical_name": "AMD Ryzen 9-7950X", "threads": 64})

            merged = store.merge_items([original], [updated])

            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0].threads, 64)
