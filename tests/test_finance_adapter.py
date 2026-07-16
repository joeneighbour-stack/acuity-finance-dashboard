from decimal import Decimal
import base64
import json
import os
import unittest
from unittest.mock import Mock, patch

from src.finance_adapter import (
    LIVE_TOTALS_WORKSHEET, ChartPoint, GoogleSheetsReader, active_clients,
    billing_by_entity, current_mrr, grr_quarterly, marketreader_snapshot,
    nrr_quarterly, FinanceDataError, load_google_credentials,
)


class FakeReader:
    def worksheets(self):
        return {"Finance": [
            ["Current Billing"], ["Client count (Current)", "12"],
            ["Current Monthly Billing", "£10,250.50"], [],
            ["Billing split per entity"], ["Entity table"],
            ["Entity", "GBP equivalent"], ["Acuity", "£8,000"],
            ["MarketReader", "£2,250.50"],
        ]}


class FinanceAdapterTests(unittest.TestCase):
    def setUp(self): self.reader = FakeReader()

    def test_typed_kpis(self):
        self.assertEqual(active_clients(self.reader), 12)
        self.assertEqual(current_mrr(self.reader), Decimal("10250.50"))

    def test_chart_dataset(self):
        self.assertEqual(billing_by_entity(self.reader), (
            ChartPoint("Acuity", Decimal("8000")),
            ChartPoint("MarketReader", Decimal("2250.50")),
        ))

    def test_quarterly_retention_percentages(self):
        class RetentionReader:
            def worksheets(self):
                return {"LIVE Totals": [
                    ["NRR (Net Revenue Retention) % Q", "94%"],
                    ["GRR (Gross Revenue Retention) % Q", "92%"],
                ]}
        self.assertEqual(nrr_quarterly(RetentionReader()), Decimal("94"))
        self.assertEqual(grr_quarterly(RetentionReader()), Decimal("92"))

    def test_missing_quarterly_retention_is_none(self):
        self.assertIsNone(nrr_quarterly(self.reader))
        self.assertIsNone(grr_quarterly(self.reader))

    def test_google_reader_defaults_to_live_totals_only(self):
        reader = GoogleSheetsReader("sheet-id", "credentials.json")
        self.assertEqual(reader.worksheet, LIVE_TOTALS_WORKSHEET)

    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_google_credentials_use_json_environment_variable(self, from_info, from_file):
        expected = Mock()
        from_info.return_value = expected
        value = json.dumps({"type": "service_account", "private_key": "line-one\\nline-two"})
        with patch.dict(os.environ, {
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": value,
            "GOOGLE_SERVICE_ACCOUNT_FILE": "must-not-be-used.json",
        }, clear=False):
            credentials = load_google_credentials()
        self.assertIs(credentials, expected)
        from_file.assert_not_called()

    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_google_credentials_use_base64_json_first(self, from_info, from_file):
        expected = Mock()
        from_info.return_value = expected
        encoded = base64.b64encode(json.dumps({
            "type": "service_account", "private_key": "first\\nsecond"
        }).encode("utf-8")).decode("ascii")
        with patch.dict(os.environ, {
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64": encoded,
            "GOOGLE_SERVICE_ACCOUNT_JSON": "must-not-be-parsed",
            "GOOGLE_SERVICE_ACCOUNT_FILE": "must-not-be-used.json",
        }, clear=False):
            credentials = load_google_credentials()
        self.assertIs(credentials, expected)
        self.assertEqual(from_info.call_args[0][0]["private_key"], "first\nsecond")
        from_file.assert_not_called()

    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_invalid_base64_has_safe_error(self, from_info):
        with patch.dict(os.environ, {
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64": "not-valid-base64!",
            "GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps({"type": "service_account"}),
        }, clear=False):
            with self.assertRaisesRegex(FinanceDataError, "Google service-account credentials are not configured correctly"):
                load_google_credentials()
        from_info.assert_not_called()

    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    def test_google_credentials_use_local_file_fallback(self, from_file):
        expected = Mock()
        from_file.return_value = expected
        with patch.dict(os.environ, {
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_FILE": "local-credentials.json",
        }, clear=False):
            credentials = load_google_credentials()
        self.assertIs(credentials, expected)
        from_file.assert_called_once_with("local-credentials.json", scopes=("https://www.googleapis.com/auth/spreadsheets.readonly",))

    def test_google_credentials_missing_has_safe_error(self):
        with patch.dict(os.environ, {
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64": "",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "",
            "GOOGLE_SERVICE_ACCOUNT_FILE": "",
        }, clear=False):
            with self.assertRaisesRegex(FinanceDataError, "Google service-account credentials are not configured correctly"):
                load_google_credentials()

    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_google_credentials_convert_escaped_private_key_newlines(self, from_info):
        value = json.dumps({"type": "service_account", "private_key": "first\\nsecond"})
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON_B64": "", "GOOGLE_SERVICE_ACCOUNT_JSON": value}, clear=False):
            load_google_credentials()
        credentials_info = from_info.call_args[0][0]
        self.assertEqual(credentials_info["private_key"], "first\nsecond")

    def test_marketreader_is_not_merged_with_acuity(self):
        class PairedReader:
            def worksheets(self):
                return {"LIVE Totals": [
                    ["Current Billing"],
                    ["Client count (Current)", "10", "", "", "Client count (Current)", "3"],
                    ["Contract count (Current)", "11", "", "", "Contract count (Current)", "4"],
                    ["Current Monthly Billing", "1000", "", "", "Current Monthly Billing", "600"],
                    ["ARR (GBP) after cancelled revenue", "12000", "", "", "ARR (GBP) after cancelled revenue", "7200"],
                    ["MRR (GBP) incl future ramp ups", "1100", "", "", "MRR (GBP) incl future ramp ups", "650"],
                    ["ARR (GBP) incl future ramp ups", "13200", "", "", "ARR (GBP) incl future ramp ups", "7800"],
                ]}
        reader = PairedReader()
        self.assertEqual(active_clients(reader), 10)
        self.assertEqual(current_mrr(reader), Decimal("1000"))
        marketreader = marketreader_snapshot(reader)
        self.assertEqual(marketreader.active_clients, 3)
        self.assertEqual(marketreader.current_mrr, Decimal("600"))


if __name__ == "__main__": unittest.main()
