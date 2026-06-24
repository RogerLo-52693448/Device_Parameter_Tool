import pytest

from src.main.python.utils.validators import (
    validate_latitude,
    validate_log_level,
    validate_longitude,
    validate_non_negative_float,
    validate_orientation,
    validate_port,
    validate_positive_float,
    validate_positive_int,
    validate_transport,
)


class TestValidateLatitude:
    def test_valid_values(self):
        assert validate_latitude(0) == 0.0
        assert validate_latitude(90) == 90.0
        assert validate_latitude(-90) == -90.0
        assert validate_latitude(25.033) == pytest.approx(25.033)

    def test_invalid_above(self):
        with pytest.raises(ValueError):
            validate_latitude(90.1)

    def test_invalid_below(self):
        with pytest.raises(ValueError):
            validate_latitude(-90.1)

    def test_string_input(self):
        assert validate_latitude("25.0") == pytest.approx(25.0)


class TestValidateLongitude:
    def test_valid_values(self):
        assert validate_longitude(0) == 0.0
        assert validate_longitude(180) == 180.0
        assert validate_longitude(-180) == -180.0

    def test_invalid_above(self):
        with pytest.raises(ValueError):
            validate_longitude(180.1)

    def test_invalid_below(self):
        with pytest.raises(ValueError):
            validate_longitude(-180.1)


class TestValidateOrientation:
    def test_valid_values(self):
        assert validate_orientation(0) == 0.0
        assert validate_orientation(360) == 360.0
        assert validate_orientation(180) == 180.0

    def test_invalid_above(self):
        with pytest.raises(ValueError):
            validate_orientation(360.1)

    def test_invalid_below(self):
        with pytest.raises(ValueError):
            validate_orientation(-1)


class TestValidatePort:
    def test_valid(self):
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535
        assert validate_port(1883) == 1883

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            validate_port(0)

    def test_invalid_too_large(self):
        with pytest.raises(ValueError):
            validate_port(65536)


class TestValidatePositiveFloat:
    def test_valid(self):
        assert validate_positive_float(0.1) == pytest.approx(0.1)
        assert validate_positive_float(3.5) == pytest.approx(3.5)

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            validate_positive_float(0)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            validate_positive_float(-1.0)


class TestValidateNonNegativeFloat:
    def test_valid_zero(self):
        assert validate_non_negative_float(0) == 0.0

    def test_valid_positive(self):
        assert validate_non_negative_float(1.5) == pytest.approx(1.5)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            validate_non_negative_float(-0.1)


class TestValidatePositiveInt:
    def test_valid(self):
        assert validate_positive_int(1) == 1
        assert validate_positive_int(30) == 30

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            validate_positive_int(0)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            validate_positive_int(-1)


class TestValidateLogLevel:
    def test_valid(self):
        assert validate_log_level("DEBUG") == "DEBUG"
        assert validate_log_level("INFO") == "INFO"
        assert validate_log_level("WARNING") == "WARNING"
        assert validate_log_level("ERROR") == "ERROR"

    def test_case_insensitive(self):
        assert validate_log_level("debug") == "DEBUG"
        assert validate_log_level("info") == "INFO"

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_log_level("VERBOSE")


class TestValidateTransport:
    def test_valid(self):
        assert validate_transport("tcp") == "tcp"
        assert validate_transport("udp") == "udp"

    def test_case_insensitive(self):
        assert validate_transport("TCP") == "tcp"

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_transport("http")
