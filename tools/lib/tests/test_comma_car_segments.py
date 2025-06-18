import pytest
import requests
from selfdrive.car.fingerprints import MIGRATION
from tools.lib.comma_car_segments import get_comma_car_segments_database, get_url
from tools.lib.logreader import LogReader
from tools.lib.route import SegmentRange


@pytest.mark.skip(reason="huggingface is flaky, run this test manually to check for issues")
class TestCommaCarSegments:
  def test_database(self):
    database = get_comma_car_segments_database()

    platforms = database.keys()

    assert len(platforms) > 100

  def test_download_segment(self):
    database = get_comma_car_segments_database()

    fp = "SUBARU_FORESTER"

    segment = database[fp][0]

    sr = SegmentRange(segment)

    url = get_url(sr.route_name, sr.slice)

    resp = requests.get(url)
    assert resp.status_code == 200

    lr = LogReader(url)
    CP = lr.first("carParams")
    assert MIGRATION.get(CP.carFingerprint, CP.carFingerprint) == fp
