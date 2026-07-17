import unittest

from src.dashboard_theme import THEME_CSS


class DashboardThemeTests(unittest.TestCase):
    def test_sales_kpi_grid_has_responsive_breakpoints(self):
        self.assertIn("grid-template-columns: repeat(4", THEME_CSS)
        self.assertIn("grid-template-columns: repeat(2", THEME_CSS)
        self.assertIn("@media (max-width: 640px)", THEME_CSS)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", THEME_CSS)


if __name__ == "__main__":
    unittest.main()
