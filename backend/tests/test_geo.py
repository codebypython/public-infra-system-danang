import pytest

from app.utils.geo import bbox_polygon_wkt, is_in_danang, parse_bbox, wkt_point


def test_wkt_point():
    assert wkt_point(108.22, 16.05) == "SRID=4326;POINT(108.22 16.05)"


def test_parse_bbox():
    assert parse_bbox("108.0,16.0,108.3,16.2") == (108.0, 16.0, 108.3, 16.2)
    with pytest.raises(ValueError):
        parse_bbox("a,b,c,d")
    with pytest.raises(ValueError):
        parse_bbox("108.0,16.0,108.0,16.2")


def test_is_in_danang():
    assert is_in_danang(108.22, 16.05)
    assert not is_in_danang(106.0, 10.0)


def test_bbox_polygon_wkt():
    wkt = bbox_polygon_wkt((108.0, 16.0, 108.3, 16.2))
    assert wkt.startswith("SRID=4326;POLYGON((")
