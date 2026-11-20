import http.client
import json
import threading
import unittest
from http.server import HTTPServer

from server import make_handler
from tillpoint import db
from tillpoint.api import App


class BadInputTest(unittest.TestCase):
    """A malformed request body must get a 400, not a dropped connection."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), make_handler(App(db.connect())))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, raw):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/orders", body=raw, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())

    def test_invalid_json_is_a_400(self):
        status, payload = self.post(b"{not json")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_json_that_is_not_an_object_is_a_400(self):
        status, _ = self.post(b"[1, 2, 3]")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
