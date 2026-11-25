import unittest
from src.spec_parser import parse_laptop_specs
from src.matcher import compute_match_score


class TestSpecMatcher(unittest.TestCase):
    def test_exact_sku_and_specs_match(self):
        ucc = parse_laptop_specs(
            "Acer Aspire 3 A315-59-562P Core i5 12th Gen 8GB RAM 512GB SSD 15.6 Inch FHD Laptop"
        )
        startech = parse_laptop_specs(
            "Acer Aspire 3 A315-59-562P Core i5-1235U 8GB DDR4 512GB NVMe SSD Laptop"
        )
        score, reason = compute_match_score(ucc, startech)
        self.assertEqual(score, 100.0)
        self.assertIn("A315-59-562P", reason)

    def test_ram_mismatch_rejected(self):
        ucc = parse_laptop_specs(
            "Acer Nitro V ANV15-51 Core i5-13420H 8GB RAM 512GB SSD RTX 4050"
        )
        ryans = parse_laptop_specs(
            "Acer Nitro V ANV15-51 Core i5-13420H 16GB RAM 512GB SSD RTX 4050"
        )
        score, reason = compute_match_score(ucc, ryans)
        self.assertEqual(score, 0.0)
        self.assertEqual(reason, "RAM Mismatch")

    def test_ssd_mismatch_rejected(self):
        ucc = parse_laptop_specs(
            "Acer Swift Go 14 SFG14-71 Core i7-13700H 16GB RAM 512GB SSD"
        )
        techland = parse_laptop_specs(
            "Acer Swift Go 14 SFG14-71 Core i7-13700H 16GB RAM 1TB SSD"
        )
        score, reason = compute_match_score(ucc, techland)
        self.assertEqual(score, 0.0)
        self.assertEqual(reason, "SSD Mismatch")

    def test_cpu_mismatch_rejected(self):
        ucc = parse_laptop_specs(
            "Acer Aspire 5 Core i5-1235U 8GB RAM 512GB SSD"
        )
        ryans = parse_laptop_specs(
            "Acer Aspire 5 Core i5-1335U 8GB RAM 512GB SSD"
        )
        score, reason = compute_match_score(ucc, ryans)
        self.assertEqual(score, 0.0)
        self.assertEqual(reason, "CPU Mismatch")

    def test_cross_store_different_title_format_matches(self):
        ucc = parse_laptop_specs(
            "Acer Aspire Lite AL15-41 Ryzen 5 5500U 16GB 512GB SSD"
        )
        ryans = parse_laptop_specs(
            "Acer Aspire Lite AMD Ryzen 5 5500U 15.6 Inch FHD Display 16GB RAM 512GB NVMe SSD"
        )
        score, _ = compute_match_score(ucc, ryans)
        self.assertGreaterEqual(score, 72.0)


if __name__ == "__main__":
    unittest.main()
